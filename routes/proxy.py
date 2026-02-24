"""
代理路由
Main proxy routes with HMAC verification, IP whitelist, and session management
"""
import os
import time
import logging
from typing import Optional

import aiofiles
from fastapi import APIRouter, Request, Response, Header, Cookie
from fastapi.responses import JSONResponse, RedirectResponse

from models.config import config
from services.stream_proxy import create_stream_proxy_service
from services.http_client import http_client_service
from services.session_service import get_or_validate_session_by_ip_ua, validate_session
from services.validation_service import validate_with_deduplication
from services.auth_service import (
    check_ip_key_path,
    check_m3u8_access_count,
    add_ip_to_whitelist,
    add_static_file_whitelist
)
from services.js_whitelist_service import check_js_whitelist
from services.access_log_service import log_access
from services.token_replay_service import check_token_replay
from services.key_protect_service import (
    modify_m3u8_key_uri,
    check_key_access,
    is_key_file,
    get_cached_m3u8_content,
    set_cached_m3u8_content,
    log_key_access
)
from utils.helpers import (
    get_client_ip,
    extract_match_key,
    validate_token,
    validate_api_key,
    create_session_cookie,
    ErrorHandler
)

logger = logging.getLogger(__name__)

router = APIRouter()


def build_no_cache_headers(response, modified_content: str = None) -> dict:
    """
    构建禁用缓存的响应头
    
    Args:
        response: 原始响应对象
        modified_content: 如果提供，将根据此内容更新 Content-Length
    
    Returns:
        dict: 包含禁用缓存的新响应头
    """
    new_headers = {}
    if hasattr(response, 'headers'):
        # 复制原有 headers，但排除可能冲突的
        for key, value in response.headers.items():
            if key.lower() not in ('content-length', 'transfer-encoding'):
                new_headers[key] = value
    
    # 如果提供了 modified_content，更新 Content-Length
    if modified_content is not None:
        new_headers['Content-Length'] = str(len(modified_content.encode('utf-8')))
    
    # 禁用缓存，确保每次都获取最新的动态内容
    new_headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    new_headers['Pragma'] = 'no-cache'
    new_headers['Expires'] = '0'
    
    return new_headers

# 全局流式代理服务（将在应用启动时初始化）
stream_proxy_service = None


def set_stream_proxy_service(service):
    """设置全局流式代理服务实例"""
    global stream_proxy_service
    stream_proxy_service = service


@router.post("/api/whitelist")
async def add_ip_whitelist_endpoint(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    添加IP到白名单
    需要 API Key 认证
    """
    client_ip = get_client_ip(request)
    
    try:
        # Validate API key
        if not validate_api_key(authorization, config.API_KEY):
            logger.warning(f"Whitelist addition failed: Invalid or missing API key from {client_ip}")
            return JSONResponse(
                content={"error": "Invalid or missing API key"},
                status_code=403
            )
        
        # Parse request data
        try:
            data = await request.json()
        except Exception:
            return JSONResponse(
                content={"error": "Invalid JSON data"},
                status_code=400
            )
        
        uid = data.get("uid")
        path = data.get("path")
        target_client_ip = data.get("clientIp")
        user_agent = data.get("UserAgent")
        
        if not uid or not path or not target_client_ip or not user_agent:
            logger.warning(f"Whitelist addition failed: Missing required fields from {client_ip}")
            return JSONResponse(
                content={"error": "uid, path, clientIp, and UserAgent are required"},
                status_code=400
            )
        
        # Add to whitelist
        result = await add_ip_to_whitelist(uid, path, target_client_ip, user_agent)
        
        if result.get("success"):
            result["worker_pid"] = os.getpid()
            return JSONResponse(content=result, status_code=200)
        else:
            return JSONResponse(content=result, status_code=400)
        
    except Exception as e:
        logger.error(f"add_ip_whitelist error: {str(e)}")
        return JSONResponse(
            content={"error": f"Failed to add IP to whitelist: {str(e)}"},
            status_code=500
        )


@router.post("/api/static-whitelist")
async def add_static_file_whitelist_endpoint(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    添加UA+IP到静态文件白名单（独立存储，无需路径）
    需要 API Key 认证
    
    请求参数:
        uid: 用户ID (必需)
        clientIp: 客户端IP (必需)
        UserAgent: User-Agent (必需)
    """
    client_ip = get_client_ip(request)
    
    try:
        # Validate API key
        if not validate_api_key(authorization, config.API_KEY):
            logger.warning(f"Static whitelist addition failed: Invalid or missing API key from {client_ip}")
            return JSONResponse(
                content={"error": "Invalid or missing API key"},
                status_code=403
            )
        
        # Parse request data
        try:
            data = await request.json()
        except Exception:
            return JSONResponse(
                content={"error": "Invalid JSON data"},
                status_code=400
            )
        
        uid = data.get("uid")
        target_client_ip = data.get("clientIp")
        user_agent = data.get("UserAgent")
        
        if not uid or not target_client_ip or not user_agent:
            logger.warning(f"Static whitelist addition failed: Missing required fields from {client_ip}")
            return JSONResponse(
                content={"error": "uid, clientIp, and UserAgent are required"},
                status_code=400
            )
        
        # Add to static file whitelist
        result = await add_static_file_whitelist(uid, target_client_ip, user_agent)
        
        if result.get("success"):
            result["worker_pid"] = os.getpid()
            return JSONResponse(content=result, status_code=200)
        else:
            return JSONResponse(content=result, status_code=400)
        
    except Exception as e:
        logger.error(f"add_static_file_whitelist error: {str(e)}")
        return JSONResponse(
            content={"error": f"Failed to add to static file whitelist: {str(e)}"},
            status_code=500
        )


@router.get("/{path:path}")
@router.head("/{path:path}")
async def proxy_handler(
    request: Request,
    path: str,
    uid: Optional[str] = None,
    expires: Optional[str] = None,
    token: Optional[str] = None,
    session_id: Optional[str] = Cookie(None, alias=config.SESSION_COOKIE_NAME),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID")
):
    """
    主代理处理器
    支持 HMAC 验证、IP 白名单、会话管理
    支持 GET 和 HEAD 方法
    """
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "unknown")
    full_url = str(request.url)
    
    # 优先使用 header 中的 session_id
    effective_session_id = x_session_id or session_id
    
    logger.debug(f"请求接收: method={request.method}, path={path}, uid={uid}, session_id={effective_session_id}, client_ip={client_ip}")
    
    # 确定请求类型
    # 检查是否为静态文件
    is_static_file = path.lower().endswith(config.STATIC_FILE_EXTENSIONS)
    
    # 使用配置中定义的完全放行扩展名（完全跳过验证的文件类型）
    if config.ENABLE_STATIC_FILE_IP_ONLY_CHECK:
        # 启用静态文件IP验证时，只跳过FULLY_ALLOWED_EXTENSIONS中的文件
        skip_validation = path.lower().endswith(config.FULLY_ALLOWED_EXTENSIONS)
        
        # DEBUG: 详细日志记录 FULLY_ALLOWED_EXTENSIONS 的使用
        if config.DEBUG_FULLY_ALLOWED_EXTENSIONS:
            logger.info(f"🔍 DEBUG FULLY_ALLOWED_EXTENSIONS:")
            logger.info(f"   配置值: {config.FULLY_ALLOWED_EXTENSIONS}")
            logger.info(f"   配置类型: {type(config.FULLY_ALLOWED_EXTENSIONS)}")
            logger.info(f"   元素数量: {len(config.FULLY_ALLOWED_EXTENSIONS)}")
            logger.info(f"   请求路径: {path}")
            logger.info(f"   小写路径: {path.lower()}")
            logger.info(f"   skip_validation 结果: {skip_validation}")
            for ext in config.FULLY_ALLOWED_EXTENSIONS:
                matches = path.lower().endswith(ext)
                logger.info(f"   - 扩展名 '{ext}': {matches}")
    else:
        # 未启用时，保持原有行为：使用传统的跳过验证扩展名列表
        skip_validation = path.lower().endswith(config.LEGACY_SKIP_VALIDATION_EXTENSIONS)
        
        # DEBUG: 详细日志记录传统验证跳过的使用
        if config.DEBUG_FULLY_ALLOWED_EXTENSIONS:
            logger.info(f"🔍 DEBUG LEGACY_SKIP_VALIDATION_EXTENSIONS:")
            logger.info(f"   配置值: {config.LEGACY_SKIP_VALIDATION_EXTENSIONS}")
            logger.info(f"   请求路径: {path}")
            logger.info(f"   skip_validation 结果: {skip_validation}")

    
    is_m3u8 = path.lower().endswith('.m3u8')
    is_ts = path.lower().endswith('.ts')
    is_enc_key = path.lower().endswith('enc.key')
    is_js = path.lower().endswith('.js')
    
    # 判断是否为索引文件（无扩展名的index/playlist等）
    path_parts = path.split('/')
    is_index_file = len(path_parts) > 0 and path_parts[-1].lower() in ('index', 'playlist', 'master')
    
    # 判断是否为静态文件（用于白名单验证）
    is_static_file = (
        is_js or is_m3u8 or is_ts or is_enc_key or is_index_file or
        path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.css', '.woff', '.woff2', '.ttf', 
                              '.mp4', '.webm', '.svg', '.ico'))
    )
    
    # 确定文件类型
    if is_m3u8:
        file_type = "m3u8"
    elif is_ts:
        file_type = "ts"
    elif is_enc_key:
        file_type = "enc_key"
    elif path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.woff', '.woff2', '.ttf')):
        file_type = "static"
    else:
        file_type = "default"
    
    new_session_created = False
    validated_session_data = None
    effective_uid = None
    backend_verified = False  # 标记是否通过后端验证（常规验证）
    
    # 如果跳过验证，默认允许访问
    if skip_validation:
        is_allowed = True
        whitelist_uid = None
        if config.DEBUG_FULLY_ALLOWED_EXTENSIONS:
            logger.info(f"⏭️ 跳过验证（FULLY_ALLOWED_EXTENSIONS）: path={path}")
        else:
            logger.debug(f"⏭️ 跳过验证（FULLY_ALLOWED_EXTENSIONS）: path={path}")
    
    # 优先执行后端验证（常规验证：IP白名单、Session等）
    # 后端提交和前端提交（JS白名单）任意一个有效即可，但优先检查后端
    if not skip_validation:
        # 使用并行验证和请求去重（如果启用）
        skip_ip_check = config.DISABLE_IP_WHITELIST or config.DISABLE_PATH_PROTECTION
        skip_session_check = config.DISABLE_SESSION_VALIDATION
        
        # 执行验证（可能是并行的或去重的，取决于配置）
        is_allowed, whitelist_uid, effective_session_id, session_uid, new_session_created, validated_session_data = \
            await validate_with_deduplication(
                client_ip, path, user_agent, uid,
                skip_ip_check=skip_ip_check,
                skip_session_check=skip_session_check
            )
        
        if skip_ip_check:
            if config.DISABLE_IP_WHITELIST:
                logger.info(f"⚠️ 测试模式：跳过 IP 白名单检查 (DISABLE_IP_WHITELIST=True)")
            if config.DISABLE_PATH_PROTECTION:
                logger.info(f"⚠️ 测试模式：跳过路径保护检查 (DISABLE_PATH_PROTECTION=True)")
        
        if skip_session_check:
            logger.info(f"⚠️ 测试模式：跳过会话验证 (DISABLE_SESSION_VALIDATION=True)")
        
        # 如果后端验证通过，标记已验证
        if is_allowed:
            backend_verified = True
            logger.debug(
                f"✅ 后端验证通过（跳过JS白名单验证）: IP={client_ip}, path={path}, uid={uid or 'none'}"
            )
    
    # 如果后端验证失败，且是静态文件，尝试JS白名单验证（前端提交）
    if not backend_verified and is_static_file and config.ENABLE_JS_WHITELIST_TRACKER:
        is_allowed, whitelist_uid = await check_js_whitelist(
            path, client_ip, user_agent, uid
        )
        # 如果通过JS白名单验证，使用白名单中的UID
        if is_allowed and whitelist_uid:
            effective_uid = whitelist_uid
            logger.info(
                f"✅ JS白名单验证通过（后端验证失败后的回退）: "
                f"path={path}, uid={effective_uid}, ip={client_ip}"
            )
        else:
            # JS白名单验证也失败了，记录详细信息
            logger.warning(
                f"❌ 访问验证失败: path={path}, ip={client_ip}, uid={uid or 'unknown'} | "
                f"后端验证=失败, JS白名单验证=失败"
            )
    
    # 最终检查：如果两种验证都失败，拒绝访问
    if not skip_validation and not is_allowed:
        # 如果后端验证通过了，则不会执行到这里
        # 如果后端验证失败且JS白名单也失败，上面已经记录了详细日志
        # 记录拒绝访问到Redis
        await log_access(
            uid=uid or effective_uid,
            ip=client_ip,
            user_agent=user_agent,
            path=path,
            allowed=False,
            reason="验证失败: 后端验证和JS白名单验证均失败"
        )
        return Response(content="Access Denied: Path not allowed", status_code=403)
    
    # 2. 对于允许访问的enc.key文件，检查是否启用Safe Key Protect重定向
    if is_allowed and is_enc_key and config.SAFE_KEY_PROTECT_ENABLED:
        redirect_url = f"{config.SAFE_KEY_PROTECT_REDIRECT_BASE_URL}{path}"
        logger.info(f"🔐 Safe Key Protect重定向: IP={client_ip}, enc.key文件={path}, redirect_to={redirect_url}")
        
        return RedirectResponse(
            url=redirect_url,
            status_code=302,
            headers={'Cache-Control': 'no-cache, no-store, must-revalidate'}
        )
    
    # 3. 处理会话和UID
    if effective_session_id and validated_session_data:
        effective_uid = session_uid or validated_session_data.get("uid")
        logger.debug(f"找到会话: session_id={effective_session_id}, uid={effective_uid}")
    
    # 4. 如果没有会话 UID，使用白名单 UID 作为后备
    if not effective_uid and whitelist_uid:
        effective_uid = whitelist_uid
        logger.debug(f"使用白名单 UID={whitelist_uid} 对于 path={path}")
        
        # 测试模式：如果仍然没有 UID，使用默认测试 UID
        if not effective_uid and skip_ip_check:
            effective_uid = "test_user"
            logger.debug(f"测试模式：使用默认 UID=test_user")
        
        # 5. 处理 .m3u8 请求的严格验证
        if is_m3u8:
            if not effective_uid:
                logger.warning(f"无有效 UID 对于 .m3u8 请求: path={path}")
                return Response(content="No valid UID for .m3u8 request", status_code=403)
            
            if not uid or not expires or not token:
                logger.warning(f".m3u8 请求缺少 HMAC 参数: path={path}")
                return Response(
                    content=".m3u8 request missing required parameters (uid, expires, token)",
                    status_code=400
                )
            
            hmac_valid = validate_token(uid, path, expires, token, config.SECRET_KEY)
            if not hmac_valid:
                logger.warning(f".m3u8 请求令牌无效或已过期: path={path}")
                return Response(content=".m3u8 request token invalid or expired", status_code=403)
            
            if not await check_m3u8_access_count(effective_uid, full_url, client_ip, user_agent):
                logger.warning(f"单次使用违规 .m3u8 路径: {path}, uid={effective_uid}")
                return Response(content=f"Access Denied: Too many accesses", status_code=403)
    
    # 6. Token 防重放保护检查
    # 对于包含 token 参数的请求，检查 token 是否已被重放使用
    # 注意：.key 文件有独立的访问次数控制（在第7步），跳过通用检查
    is_protected_key_file = config.KEY_PROTECT_ENABLED and is_key_file(path, config.KEY_PROTECT_EXTENSIONS)
    
    if config.TOKEN_REPLAY_ENABLED and token and uid and not is_protected_key_file:
        replay_allowed, replay_info = await check_token_replay(
            token=token,
            uid=uid,
            path=path,
            max_uses=config.TOKEN_REPLAY_MAX_USES,
            ttl=config.TOKEN_REPLAY_TTL,
            client_ip=client_ip,
            user_agent=user_agent,
            full_url=full_url
        )
        
        if not replay_allowed:
            logger.warning(
                f"Token 重放攻击被阻止: path={path}, uid={uid}, ip={client_ip}, "
                f"count={replay_info.get('current_count')}/{replay_info.get('max_uses')}"
            )
            # 记录拒绝访问到Redis
            await log_access(
                uid=uid,
                ip=client_ip,
                user_agent=user_agent,
                path=path,
                allowed=False,
                reason=f"Token replay detected: {replay_info.get('reason', 'max uses exceeded')}"
            )
            # 提供更详细的错误信息
            remaining_ttl = replay_info.get('remaining_ttl', config.TOKEN_REPLAY_TTL)
            return Response(
                content=f"Access Denied: Token has exceeded maximum usage limit ({replay_info.get('max_uses', 1)} uses). "
                        f"Please request a new token. TTL: {remaining_ttl}s",
                status_code=403
            )
    
    # 7. Key 文件动态保护检查（独立的访问次数控制）
    # 对于 .key 文件请求，验证 token 参数并使用 KEY_PROTECT_MAX_USES 配置
    if is_protected_key_file:
        # .key 请求应该带有 uid、token、expires 参数（由动态修改的 m3u8 传递）
        if not uid or not token:
            logger.warning(f"🔐 Key 文件访问被拒绝（缺少验证参数）: path={path}, ip={client_ip}")
            await log_access(
                uid="unknown",
                ip=client_ip,
                user_agent=user_agent,
                path=path,
                allowed=False,
                reason="Key file access denied: missing uid or token parameter"
            )
            return Response(
                content="Access Denied: Missing authentication parameters for key file",
                status_code=403
            )
        
        # 验证 expires 时间戳 - 必需参数
        if not expires:
            logger.warning(f"🔐 Key 文件访问被拒绝（缺少 expires 参数）: path={path}, uid={uid}, ip={client_ip}")
            await log_access(
                uid=uid,
                ip=client_ip,
                user_agent=user_agent,
                path=path,
                allowed=False,
                reason="Key file access denied: missing expires parameter"
            )
            return Response(
                content="Access Denied: Missing expires parameter for key file",
                status_code=403
            )
        
        # 验证 HMAC token（使用 key 文件路径生成的独立 token）
        # 现在 token 是为 key 文件路径专门生成的，可以验证 HMAC
        key_hmac_valid = validate_token(uid, path, expires, token, config.SECRET_KEY)
        if not key_hmac_valid:
            logger.warning(f"🔐 Key 文件 token 无效或已过期: path={path}, uid={uid}, ip={client_ip}")
            # 记录到 Key 访问日志（HMAC 无效时记录）
            await log_key_access(
                uid=uid,
                key_path=path,
                client_ip=client_ip,
                is_blocked=True,
                current_count=0,
                max_uses=config.KEY_PROTECT_MAX_USES,
                reason="hmac_invalid",
                user_agent=user_agent
            )
            return Response(
                content="Access Denied: Key file token invalid or expired",
                status_code=403
            )
        
        # 检查访问次数限制
        key_allowed, key_info = await check_key_access(
            key_path=path,
            uid=uid,
            token=token,
            client_ip=client_ip,
            max_uses=config.KEY_PROTECT_MAX_USES,
            ttl=config.KEY_PROTECT_TTL,
            user_agent=user_agent
        )
        
        if not key_allowed:
            logger.warning(
                f"🔐 Key 文件重放攻击被阻止: path={path}, uid={uid}, ip={client_ip}, "
                f"reason={key_info.get('reason', 'unknown')}"
            )
            await log_access(
                uid=uid,
                ip=client_ip,
                user_agent=user_agent,
                path=path,
                allowed=False,
                reason=f"Key file replay detected: {key_info.get('reason', 'access denied')}"
            )
            return Response(
                content=f"Access Denied: {key_info.get('reason', 'Key file access not allowed')}",
                status_code=403
            )
        
        logger.info(
            f"🔑 Key 文件访问允许: path={path}, uid={uid}, "
            f"count={key_info.get('current_count', 0)}/{key_info.get('max_uses', 0)}"
        )
    
    # 代理请求到后端
    if config.BACKEND_MODE == "filesystem":
        # 文件系统模式：直接传递文件路径
        try:
            response = await stream_proxy_service.proxy_stream(
                file_path=path,
                request=request,
                chunk_size=config.STREAM_CHUNK_SIZE,
                uid=effective_uid,
                session_id=effective_session_id,
                file_type=file_type,
                client_ip=client_ip
            )
        except Exception as e:
            if ErrorHandler.is_client_disconnect_error(e):
                if not ErrorHandler.should_suppress_logging(e):
                    logger.debug(f"客户端断开连接: {path} - {str(e)}")
                return Response(content="Client Closed Request", status_code=499)
            else:
                err_msg = str(e)
                logger.error(f"文件系统代理失败: {path} - {err_msg}")
                return Response(content=f"Filesystem proxy failed: {err_msg}", status_code=502)
    
    elif config.BACKEND_MODE == "http":
        # HTTP 模式：构建远程 URL
        backend_scheme = "https" if config.BACKEND_USE_HTTPS else "http"
        remote_url = f"{backend_scheme}://{config.BACKEND_HOST}:{config.BACKEND_PORT}/{path}"
        
        headers = {
            "User-Agent": user_agent,
            "Host": config.PROXY_HOST_HEADER,
            "X-Forwarded-For": client_ip
        }
        
        # 添加原始请求头（如果需要）
        for header_name in ["Range", "If-Range", "If-Modified-Since", "If-None-Match"]:
            if header_name.lower() in request.headers:
                headers[header_name] = request.headers[header_name]
        
        try:
            # 使用流式代理服务
            response = await stream_proxy_service.proxy_stream(
                remote_url=remote_url,
                headers=headers,
                request=request,
                chunk_size=config.STREAM_CHUNK_SIZE,
                uid=effective_uid,
                session_id=effective_session_id,
                file_type=file_type,
                client_ip=client_ip
            )
        except Exception as e:
            if ErrorHandler.is_client_disconnect_error(e):
                if not ErrorHandler.should_suppress_logging(e):
                    logger.debug(f"客户端断开连接: {remote_url} - {str(e)}")
                return Response(content="Client Closed Request", status_code=499)
            else:
                err_msg = str(e)
                logger.error(f"HTTP代理失败: {remote_url} - {err_msg}")
                return Response(content=f"HTTP proxy failed: {err_msg}", status_code=502)
    
    else:
        logger.error(f"不支持的后端模式: {config.BACKEND_MODE}")
        return Response(content="Unsupported backend mode", status_code=500)
    
    # 8. 对于 m3u8 文件，动态修改内容添加 key 保护参数
    # 当 KEY_PROTECT_ENABLED 和 KEY_PROTECT_DYNAMIC_M3U8 都启用时
    if is_m3u8 and config.KEY_PROTECT_ENABLED and config.KEY_PROTECT_DYNAMIC_M3U8:
        if uid and token and expires:
            try:
                original_content = None
                cache_hit = False
                
                # 优先从 Redis 缓存获取 m3u8 原始内容
                if config.M3U8_CONTENT_CACHE_ENABLED:
                    original_content = await get_cached_m3u8_content(path)
                    if original_content:
                        cache_hit = True
                
                # 缓存未命中，从文件系统或响应中读取
                if not original_content:
                    if config.BACKEND_MODE == "filesystem":
                        file_full_path = os.path.join(config.BACKEND_FILESYSTEM_ROOT, path)
                        if os.path.exists(file_full_path):
                            # 使用异步文件 I/O
                            async with aiofiles.open(file_full_path, 'r', encoding='utf-8') as f:
                                original_content = await f.read()
                            # 缓存到 Redis
                            if config.M3U8_CONTENT_CACHE_ENABLED and original_content:
                                await set_cached_m3u8_content(
                                    path=path,
                                    content=original_content,
                                    ttl=config.M3U8_CONTENT_CACHE_TTL
                                )
                    elif hasattr(response, 'body'):
                        # 普通 Response，直接获取 body
                        original_content = response.body.decode('utf-8')
                    elif hasattr(response, 'body_iterator'):
                        # StreamingResponse，需要收集所有内容
                        # 注意：这会消耗迭代器，需要创建新响应
                        chunks = []
                        async for chunk in response.body_iterator:
                            if isinstance(chunk, bytes):
                                chunks.append(chunk)
                            else:
                                chunks.append(chunk.encode('utf-8'))
                        original_content = b''.join(chunks).decode('utf-8')
                
                if original_content:
                    # 获取 m3u8 文件所在目录（用于计算 key 文件的完整路径）
                    m3u8_dir = os.path.dirname(path)
                    
                    # 动态修改 m3u8 内容，为每个 key 文件生成独立的 HMAC token
                    modified_content = modify_m3u8_key_uri(
                        m3u8_content=original_content,
                        uid=uid,
                        expires=expires,
                        secret_key=config.SECRET_KEY,
                        m3u8_dir=m3u8_dir
                    )
                    
                    cache_status = "缓存命中" if cache_hit else "从文件读取"
                    logger.info(
                        f"🔐 M3U8 动态修改完成: path={path}, uid={uid}, "
                        f"original_len={len(original_content)}, modified_len={len(modified_content)}, "
                        f"来源={cache_status}"
                    )
                    
                    # 创建新的响应（使用 helper 函数构建禁用缓存的响应头）
                    new_headers = build_no_cache_headers(response, modified_content)
                    
                    response = Response(
                        content=modified_content,
                        status_code=response.status_code if hasattr(response, 'status_code') else 200,
                        headers=new_headers,
                        media_type='application/vnd.apple.mpegurl'
                    )
            except Exception as e:
                logger.error(f"动态修改 m3u8 失败: path={path}, error={str(e)}")
                # 修改失败时，对于文件系统模式可以重新获取原始响应
                if config.BACKEND_MODE == "filesystem":
                    try:
                        response = await stream_proxy_service.proxy_stream(
                            file_path=path,
                            request=request,
                            chunk_size=config.STREAM_CHUNK_SIZE,
                            uid=effective_uid,
                            session_id=effective_session_id,
                            file_type=file_type,
                            client_ip=client_ip
                        )
                        logger.warning(f"M3U8 动态修改失败，返回原始内容: path={path}")
                    except Exception as retry_error:
                        logger.error(f"重新获取 m3u8 失败: {str(retry_error)}")
    
    # 9. 对于 key 文件，禁用缓存确保每次都验证访问权限
    if is_protected_key_file and hasattr(response, 'headers'):
        # 添加禁用缓存的响应头
        no_cache_headers = build_no_cache_headers(response)
        for header_key, header_value in no_cache_headers.items():
            response.headers[header_key] = header_value
        logger.debug(f"🔑 Key 文件禁用缓存: path={path}")
    
    # 仅在创建新会话时设置 cookie
    if new_session_created and effective_session_id:
        cookie_config = {
            'name': config.SESSION_COOKIE_NAME,
            'httponly': config.COOKIE_HTTPONLY,
            'secure': config.COOKIE_SECURE,
            'samesite': config.COOKIE_SAMESITE
        }
        cookie_str = create_session_cookie(effective_session_id, config.SESSION_TTL, cookie_config)
        response.headers["Set-Cookie"] = cookie_str
        logger.info(f"设置新会话 cookie: {effective_session_id}, ttl={config.SESSION_TTL}s")
    
    # 记录成功访问到Redis
    await log_access(
        uid=effective_uid,
        ip=client_ip,
        user_agent=user_agent,
        path=path,
        allowed=True
    )
    
    return response
