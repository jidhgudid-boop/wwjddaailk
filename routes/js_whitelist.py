"""
JS白名单追踪路由
JavaScript whitelist tracking routes
"""
import logging
from typing import Optional

from fastapi import APIRouter, Request, Header, Response, Query
from fastapi.responses import JSONResponse

from models.config import config
from services.js_whitelist_service import (
    add_js_whitelist,
    check_js_whitelist,
    get_js_whitelist_stats
)
from utils.helpers import (
    get_client_ip,
    validate_api_key,
    validate_token
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/js-whitelist")
@router.get("/api/js-whitelist")
async def add_js_whitelist_endpoint(
    request: Request,
    uid: Optional[str] = Query(None),
    jsPath: Optional[str] = Query(None, alias="js_path"),
    expires: Optional[str] = Query(None),
    sign: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    """
    添加JS文件访问到白名单
    
    支持两种认证方式:
    1. 后端服务器调用: 使用 API Key 认证 (Header: Authorization) - POST请求
    2. 前端调用: 使用 HMAC 签名认证 (Query: uid, js_path, expires, sign) - GET或POST请求
    
    UA和IP会从本服务器的请求中自动获取，无需JS传输
    
    支持两种访问模式:
    - 指定路径: jsPath为具体路径，只允许访问该路径
    - 通配符模式: jsPath为空字符串，允许该IP+UA访问所有静态文件
    
    方式1 - API Key (后端服务器) - POST:
        Header: Authorization: ******
        Body: {"uid": "user123", "jsPath": "/static/js/app.js"}
        或: {"uid": "user123", "jsPath": ""}  # 通配符模式
    
    方式2 - HMAC签名 (前端) - GET或POST:
        Query: ?uid=user123&js_path=/static/js/app.js&expires=1234567890&sign=xxx
        或: ?uid=user123&js_path=&expires=1234567890&sign=xxx  # 通配符模式
    
    注意: clientIp和UserAgent会自动从请求头中提取
    """
    if not config.ENABLE_JS_WHITELIST_TRACKER:
        return JSONResponse(
            content={
                "error": "JS whitelist tracker is disabled",
                "enabled": False
            },
            status_code=503
        )
    
    # 从请求中自动获取 IP 和 UA
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "unknown")
    
    try:
        # 判断使用哪种认证方式
        use_api_key = authorization is not None
        use_hmac_sign = sign is not None and expires is not None
        
        final_uid = None
        final_js_path = None
        
        if use_api_key:
            # 方式1: API Key 认证（后端服务器调用）
            if not validate_api_key(authorization, config.API_KEY):
                logger.warning(
                    f"JS whitelist addition failed: Invalid API key from {client_ip}"
                )
                return JSONResponse(
                    content={"error": "Invalid or missing API key"},
                    status_code=403
                )
            
            # 从请求体获取参数（仅POST请求）
            if request.method == "POST":
                try:
                    data = await request.json()
                    final_uid = data.get("uid")
                    final_js_path = data.get("jsPath", "")  # 允许空路径，默认为空字符串
                except Exception:
                    return JSONResponse(
                        content={"error": "Invalid JSON data"},
                        status_code=400
                    )
            else:
                # GET请求时，API Key方式不支持
                return JSONResponse(
                    content={"error": "API Key authentication requires POST method"},
                    status_code=400
                )
        
        elif use_hmac_sign:
            # 方式2: HMAC签名认证（前端调用）
            final_uid = uid
            final_js_path = jsPath if jsPath is not None else ""  # 允许空路径
            
            if not final_uid:
                return JSONResponse(
                    content={"error": "uid is required for HMAC auth"},
                    status_code=400
                )
            
            # 验证HMAC签名 - 使用JS白名单专用密钥
            if not validate_token(final_uid, final_js_path, expires, sign, config.JS_WHITELIST_SECRET_KEY):
                logger.warning(
                    f"JS whitelist addition failed: Invalid HMAC signature from {client_ip}"
                )
                return JSONResponse(
                    content={"error": "Invalid or expired signature"},
                    status_code=403
                )
            
            mode = "通配符" if final_js_path == "" else f"path={final_js_path}"
            logger.info(f"✅ HMAC签名验证通过: uid={final_uid}, {mode}")
        
        else:
            # 没有提供任何认证方式
            return JSONResponse(
                content={
                    "error": "Authentication required: use either API Key or HMAC signature"
                },
                status_code=401
            )
        
        if not final_uid:
            logger.warning(
                f"JS whitelist addition failed: Missing required fields from {client_ip}"
            )
            return JSONResponse(
                content={"error": "uid is required"},
                status_code=400
            )
        
        # final_js_path can be empty string for wildcard access
        if final_js_path is None:
            final_js_path = ""
        
        # Add to JS whitelist - 使用从请求中获取的 IP 和 UA
        result = await add_js_whitelist(final_uid, final_js_path, client_ip, user_agent)
        
        if result.get("success"):
            return JSONResponse(content=result, status_code=200)
        else:
            return JSONResponse(content=result, status_code=400)
        
    except Exception as e:
        logger.error(f"add_js_whitelist error: {str(e)}")
        return JSONResponse(
            content={"error": f"Failed to add to JS whitelist: {str(e)}"},
            status_code=500
        )


@router.get("/api/js-whitelist/stats")
async def get_js_whitelist_stats_endpoint(
    request: Request,
    uid: str = Query(..., description="用户ID"),
    authorization: Optional[str] = Header(None)
):
    """
    获取用户的JS白名单统计信息
    需要 API Key 认证
    
    查询参数:
        uid: 用户ID (必需)
    """
    if not config.ENABLE_JS_WHITELIST_TRACKER:
        return JSONResponse(
            content={
                "error": "JS whitelist tracker is disabled",
                "enabled": False
            },
            status_code=503
        )
    
    client_ip = get_client_ip(request)
    
    try:
        # Validate API key
        if not validate_api_key(authorization, config.API_KEY):
            logger.warning(
                f"JS whitelist stats failed: Invalid or missing API key from {client_ip}"
            )
            return JSONResponse(
                content={"error": "Invalid or missing API key"},
                status_code=403
            )
        
        # Get stats
        stats = await get_js_whitelist_stats(uid)
        
        return JSONResponse(content=stats, status_code=200)
        
    except Exception as e:
        logger.error(f"get_js_whitelist_stats error: {str(e)}")
        return JSONResponse(
            content={"error": f"Failed to get JS whitelist stats: {str(e)}"},
            status_code=500
        )


@router.get("/api/js-whitelist/check")
async def check_js_whitelist_endpoint(
    request: Request,
    js_path: str = Query(..., description="JS文件路径"),
    uid: Optional[str] = Query(None, description="用户ID（可选）")
):
    """
    检查当前请求是否有权访问指定的JS文件
    无需API Key，使用请求的IP和UA进行验证
    
    查询参数:
        js_path: JS文件路径 (必需)
        uid: 用户ID (可选)
    
    返回:
        is_allowed: 是否允许访问
        uid: 匹配的用户ID (如果找到)
    """
    if not config.ENABLE_JS_WHITELIST_TRACKER:
        return JSONResponse(
            content={
                "is_allowed": True,
                "enabled": False,
                "message": "JS whitelist tracker is disabled, access allowed by default"
            },
            status_code=200
        )
    
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "unknown")
    
    try:
        # Check whitelist
        is_allowed, whitelist_uid = await check_js_whitelist(
            js_path, client_ip, user_agent, uid
        )
        
        return JSONResponse(
            content={
                "is_allowed": is_allowed,
                "js_path": js_path,
                "uid": whitelist_uid or uid,
                "client_ip": client_ip
            },
            status_code=200 if is_allowed else 403
        )
        
    except Exception as e:
        logger.error(f"check_js_whitelist error: {str(e)}")
        return JSONResponse(
            content={"error": f"Failed to check JS whitelist: {str(e)}"},
            status_code=500
        )
