"""
Key 文件动态保护服务
通过动态修改 m3u8 文件中的 key URI 实现 .key 文件访问控制，防止重放攻击

功能说明：
- 当用户请求 m3u8 文件时，动态修改文件内容
- 在 #EXT-X-KEY 标签的 URI 中添加 uid、token、expires 参数
- 这样播放器请求 .key 文件时会自动带上这些参数
- 使用现有的 token 验证机制进行访问控制

工作原理：
1. 用户请求 m3u8 文件：/video/index.m3u8?uid=315&expires=xxx&token=xxx
2. 系统读取原始 m3u8 内容
3. 找到 #EXT-X-KEY:METHOD=AES-128,URI="enc.key" 
4. 动态修改为 #EXT-X-KEY:METHOD=AES-128,URI="enc.key?uid=315&expires=xxx&token=xxx"
5. 播放器请求 enc.key?uid=315&expires=xxx&token=xxx
6. 系统使用现有 token 验证机制检查访问权限

配置项（在 models/config.py 中）：
- KEY_PROTECT_ENABLED: 是否启用 .key 文件动态保护
- KEY_PROTECT_DYNAMIC_M3U8: 是否动态修改 m3u8 内容
- KEY_PROTECT_MAX_USES: 每个 token 关联的 .key 文件最大访问次数
- KEY_PROTECT_TTL: key 保护记录的 TTL（秒）
- KEY_PROTECT_EXTENSIONS: 需要保护的密钥文件扩展名（支持扩展名和文件名模式）
"""
import asyncio
import json
import logging
import hashlib
import hmac
import time
import re
import os
from typing import Tuple, Dict, Any, Optional, List
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

from services.redis_service import redis_service

logger = logging.getLogger(__name__)

# Redis key prefixes
KEY_PROTECT_ACCESS_PREFIX = "key_protect:access:"  # 存储 key 文件访问计数
KEY_PROTECT_LOG_KEY = "key_protect:logs"  # 存储访问日志
M3U8_CONTENT_CACHE_PREFIX = "m3u8_content:"  # 存储 m3u8 原始内容缓存
MAX_LOG_RECORDS = 300

# Background task set to prevent garbage collection of fire-and-forget tasks
_background_tasks = set()


def _schedule_background_task(coro):
    """
    Schedule a coroutine as a fire-and-forget background task.
    Prevents garbage collection and handles exceptions gracefully.
    """
    def _task_done_callback(task):
        _background_tasks.discard(task)
        try:
            exc = task.exception()
            if exc:
                logger.error(f"Background task failed: {exc}")
        except asyncio.CancelledError:
            pass
        except asyncio.InvalidStateError:
            pass
    
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_task_done_callback)
    return task


async def get_cached_m3u8_content(path: str) -> Optional[str]:
    """
    从 Redis 获取缓存的 m3u8 原始内容
    
    Args:
        path: m3u8 文件路径
    
    Returns:
        缓存的 m3u8 内容，如果不存在则返回 None
    """
    try:
        redis_client = redis_service.get_client()
        
        # 使用路径的哈希作为 key
        path_hash = hashlib.sha256(path.encode()).hexdigest()[:32]
        cache_key = f"{M3U8_CONTENT_CACHE_PREFIX}{path_hash}"
        
        cached_content = await redis_client.get(cache_key)
        
        if cached_content:
            logger.debug(f"📦 M3U8 缓存命中: path={path}")
            # Redis 返回的可能是 bytes
            if isinstance(cached_content, bytes):
                return cached_content.decode('utf-8')
            return cached_content
        
        logger.debug(f"📦 M3U8 缓存未命中: path={path}")
        return None
        
    except Exception as e:
        logger.error(f"获取 m3u8 缓存失败: path={path}, error={str(e)}")
        return None


async def set_cached_m3u8_content(path: str, content: str, ttl: int) -> bool:
    """
    将 m3u8 原始内容存入 Redis 缓存
    
    Args:
        path: m3u8 文件路径
        content: m3u8 原始内容
        ttl: 缓存 TTL（秒）
    
    Returns:
        是否成功缓存
    """
    try:
        redis_client = redis_service.get_client()
        
        # 使用路径的哈希作为 key
        path_hash = hashlib.sha256(path.encode()).hexdigest()[:32]
        cache_key = f"{M3U8_CONTENT_CACHE_PREFIX}{path_hash}"
        
        await redis_client.setex(cache_key, ttl, content)
        
        logger.debug(f"📦 M3U8 已缓存: path={path}, ttl={ttl}s, size={len(content)}")
        return True
        
    except Exception as e:
        logger.error(f"设置 m3u8 缓存失败: path={path}, error={str(e)}")
        return False


def generate_key_token(uid: str, key_path: str, expires: str, secret_key: bytes) -> str:
    """
    为 key 文件生成独立的 HMAC token
    
    Args:
        uid: 用户 ID
        key_path: key 文件的完整路径
        expires: 过期时间戳
        secret_key: HMAC 密钥
    
    Returns:
        十六进制格式的 HMAC token
    """
    msg = f"{uid}:{key_path}:{expires}".encode()
    hmac_obj = hmac.new(secret_key, msg, hashlib.sha256)
    return hmac_obj.hexdigest()


def modify_m3u8_key_uri(
    m3u8_content: str,
    uid: str,
    expires: str,
    secret_key: bytes,
    m3u8_dir: str = ""
) -> str:
    """
    动态修改 m3u8 文件内容，在 EXT-X-KEY 标签的 URI 中添加验证参数
    
    将原始的:
    #EXT-X-KEY:METHOD=AES-128,URI="enc.key",IV=0x...
    
    修改为:
    #EXT-X-KEY:METHOD=AES-128,URI="enc.key?uid=315&expires=xxx&token=xxx",IV=0x...
    
    注意：
    - 只修改 #EXT-X-KEY 标签中的 URI，不影响其他标签（如 #EXT-X-MAP）
    - 为每个 key 文件生成独立的 HMAC token（使用 key 文件路径计算）
    
    Args:
        m3u8_content: 原始 m3u8 文件内容
        uid: 用户 ID
        expires: 过期时间戳
        secret_key: HMAC 密钥（用于生成 key 文件的独立 token）
        m3u8_dir: m3u8 文件所在目录（用于计算 key 文件的完整路径）
    
    Returns:
        修改后的 m3u8 内容
    """
    if not m3u8_content:
        return m3u8_content
    
    def replace_ext_x_key_line(match):
        """
        替换整个 #EXT-X-KEY 行中的 URI
        match.group(0) = 整行 (#EXT-X-KEY:...)
        """
        line = match.group(0)
        
        # 在行内匹配 URI 属性
        def replace_uri(uri_match):
            if uri_match.group(1):  # 带引号的情况
                quote_char = uri_match.group(1)
                uri_value = uri_match.group(2)
            else:  # 不带引号的情况
                quote_char = '"'
                uri_value = uri_match.group(3)
            
            # 计算 key 文件的完整路径（用于生成独立 token）
            if uri_value.startswith('http://') or uri_value.startswith('https://'):
                # 绝对 URL，提取路径部分
                parsed = urlparse(uri_value)
                key_path = parsed.path.lstrip('/')
            elif uri_value.startswith('/'):
                # 绝对路径
                key_path = uri_value.lstrip('/')
            else:
                # 相对路径，与 m3u8 目录组合
                if m3u8_dir:
                    key_path = os.path.join(m3u8_dir, uri_value).replace('\\', '/')
                else:
                    key_path = uri_value
            
            # 为这个 key 文件生成独立的 token
            key_token = generate_key_token(uid, key_path, expires, secret_key)
            
            # 构建查询参数
            params = urlencode({
                'uid': uid,
                'expires': expires,
                'token': key_token
            })
            
            # 检查 URI 是否已经有查询参数
            if '?' in uri_value:
                new_uri = f"{uri_value}&{params}"
            else:
                new_uri = f"{uri_value}?{params}"
            
            return f'URI={quote_char}{new_uri}{quote_char}'
        
        # 匹配 URI="xxx" 或 URI='xxx' 或 URI=xxx
        uri_pattern = r'URI=(["\'])([^"\']+)\1|URI=([^\s,]+)'
        modified_line = re.sub(uri_pattern, replace_uri, line)
        
        return modified_line
    
    # 只匹配 #EXT-X-KEY 行（确保不影响其他标签）
    ext_x_key_pattern = r'^#EXT-X-KEY:.*$'
    modified_content = re.sub(ext_x_key_pattern, replace_ext_x_key_line, m3u8_content, flags=re.MULTILINE)
    
    return modified_content


async def check_key_access(
    key_path: str,
    uid: str,
    token: str,
    client_ip: str,
    max_uses: int,
    ttl: int,
    user_agent: Optional[str] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    检查 .key 文件访问是否允许
    
    基于 token 检查访问次数是否超过限制
    
    Args:
        key_path: .key 文件路径
        uid: 用户 ID（从 URL 参数获取）
        token: 验证 token（从 URL 参数获取）
        client_ip: 客户端 IP
        max_uses: 最大访问次数
        ttl: 访问计数的 TTL（秒）
        user_agent: User-Agent（可选，用于日志）
    
    Returns:
        Tuple[bool, Dict[str, Any]]: 
            - bool: True 表示允许访问，False 表示被拒绝
            - Dict: 包含详细信息的字典
    """
    redis_client = redis_service.get_client()
    
    try:
        # 生成访问计数的 Redis key
        # 使用 token + uid + key_path 组合，确保唯一性
        access_key_content = f"{token}:{uid}:{key_path}"
        access_hash = hashlib.sha256(access_key_content.encode()).hexdigest()[:32]
        access_redis_key = f"{KEY_PROTECT_ACCESS_PREFIX}{access_hash}"
        
        # 使用 INCR 原子操作递增计数器
        current_count = await redis_client.incr(access_redis_key)
        
        # 首次访问时设置 TTL
        if current_count == 1:
            await redis_client.expire(access_redis_key, ttl)
            
            logger.info(
                f"🔑 Key 文件首次访问: key_path={key_path}, uid={uid}, "
                f"ip={client_ip}, max_uses={max_uses}"
            )
            
            # 正常访问不记录日志，只记录异常情况（HMAC错误、重放）
            
            return True, {
                "allowed": True,
                "current_count": current_count,
                "max_uses": max_uses,
                "remaining_uses": max_uses - current_count,
                "is_first_use": True,
                "uid": uid
            }
        
        # 检查是否超过最大使用次数
        if current_count <= max_uses:
            remaining_ttl = await redis_client.ttl(access_redis_key)
            
            logger.info(
                f"🔑 Key 文件访问允许: key_path={key_path}, uid={uid}, "
                f"count={current_count}/{max_uses}, ip={client_ip}"
            )
            
            # 正常访问不记录日志，只记录异常情况（HMAC错误、重放）
            
            return True, {
                "allowed": True,
                "current_count": current_count,
                "max_uses": max_uses,
                "remaining_uses": max_uses - current_count,
                "is_first_use": False,
                "uid": uid,
                "remaining_ttl": remaining_ttl
            }
        else:
            # 超过最大使用次数
            remaining_ttl = await redis_client.ttl(access_redis_key)
            
            logger.warning(
                f"🚫 Key 文件重放检测: key_path={key_path}, uid={uid}, "
                f"count={current_count}/{max_uses}, ip={client_ip}"
            )
            
            # 记录被阻止的访问
            _schedule_background_task(log_key_access(
                uid=uid,
                key_path=key_path,
                client_ip=client_ip,
                is_blocked=True,
                current_count=current_count,
                max_uses=max_uses,
                reason="max_uses_exceeded",
                user_agent=user_agent
            ))
            
            return False, {
                "allowed": False,
                "current_count": current_count,
                "max_uses": max_uses,
                "remaining_uses": 0,
                "exceeded": True,
                "uid": uid,
                "remaining_ttl": remaining_ttl,
                "reason": "Key file replay detected: maximum usage count exceeded"
            }
            
    except Exception as e:
        logger.error(f"检查 key 文件访问失败: {str(e)}")
        # 出错时默认允许访问，避免因 Redis 故障导致服务不可用
        return True, {
            "allowed": True,
            "error": str(e),
            "fallback": True
        }


async def log_key_access(
    uid: str,
    key_path: str,
    client_ip: str,
    is_blocked: bool,
    current_count: int = 0,
    max_uses: int = 0,
    reason: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None:
    """
    记录 key 文件访问事件到 Redis 日志列表
    
    Args:
        uid: 用户 ID
        key_path: key 文件路径
        client_ip: 客户端 IP
        is_blocked: 是否被阻止
        current_count: 当前访问次数
        max_uses: 最大允许次数
        reason: 阻止原因（可选）
        user_agent: User-Agent（可选）
    """
    try:
        redis_client = redis_service.get_client()
        
        # 创建日志记录
        log_record = {
            "type": "key_access",
            "uid": uid,
            "path": key_path,
            "ip": client_ip,
            "ua": user_agent[:200] if user_agent else None,
            "count": current_count,
            "max_uses": max_uses,
            "blocked": is_blocked,
            "reason": reason,
            "timestamp": int(time.time())
        }
        
        # 序列化为 JSON
        record_json = json.dumps(log_record)
        
        # 使用 pipeline 批量执行所有操作
        pipe = redis_client.pipeline()
        pipe.lpush(KEY_PROTECT_LOG_KEY, record_json)
        pipe.ltrim(KEY_PROTECT_LOG_KEY, 0, MAX_LOG_RECORDS - 1)
        pipe.expire(KEY_PROTECT_LOG_KEY, 7 * 24 * 60 * 60)  # 7天过期
        await pipe.execute()
        
    except Exception as e:
        # 记录日志失败不应该影响正常请求
        logger.error(f"记录 key 文件访问事件失败: {str(e)}")


async def get_key_access_logs(limit: int = 300) -> List[Dict[str, Any]]:
    """
    获取 key 文件访问日志记录
    
    Args:
        limit: 返回的最大记录数（最多300条）
        
    Returns:
        List of key access log records
    """
    try:
        redis_client = redis_service.get_client()
        
        # 确保 limit 不超过最大值
        limit = min(limit, MAX_LOG_RECORDS)
        
        # 获取列表中的记录
        records = await redis_client.lrange(KEY_PROTECT_LOG_KEY, 0, limit - 1)
        
        # 解析 JSON 记录
        access_logs = []
        for record in records:
            try:
                access_logs.append(json.loads(record))
            except json.JSONDecodeError:
                logger.error(f"解析 key 访问日志记录失败: {record}")
                continue
        
        return access_logs
        
    except Exception as e:
        logger.error(f"获取 key 访问日志失败: {str(e)}")
        return []


async def get_key_access_summary() -> Dict[str, Any]:
    """
    获取 key 文件访问日志摘要统计
    
    Returns:
        Summary statistics
    """
    try:
        redis_client = redis_service.get_client()
        
        total_count = await redis_client.llen(KEY_PROTECT_LOG_KEY)
        
        # 获取最近的一些记录来计算被阻止的数量
        recent_records = await redis_client.lrange(KEY_PROTECT_LOG_KEY, 0, 99)
        blocked_count = 0
        max_exceeded_count = 0
        
        for record in recent_records:
            try:
                data = json.loads(record)
                if data.get("blocked"):
                    blocked_count += 1
                    reason = data.get("reason", "")
                    if reason == "max_uses_exceeded":
                        max_exceeded_count += 1
            except json.JSONDecodeError:
                continue
        
        return {
            "total_count": total_count,
            "recent_blocked_count": blocked_count,
            "recent_max_exceeded_count": max_exceeded_count,
            "max_records": MAX_LOG_RECORDS
        }
        
    except Exception as e:
        logger.error(f"获取 key 访问日志摘要失败: {str(e)}")
        return {
            "total_count": 0,
            "recent_blocked_count": 0,
            "recent_max_exceeded_count": 0,
            "max_records": MAX_LOG_RECORDS
        }


def is_key_file(path: str, extensions: tuple) -> bool:
    """
    检查路径是否为需要保护的密钥文件
    
    Args:
        path: 请求路径
        extensions: 需要保护的扩展名元组
    
    Returns:
        bool: 是否为密钥文件
    """
    if not path:
        return False
    
    path_lower = path.lower()
    for ext in extensions:
        if path_lower.endswith(ext.lower()):
            return True
    return False


async def get_m3u8_cache_stats() -> Dict[str, Any]:
    """
    获取 m3u8 缓存统计信息
    
    Returns:
        Dict containing cache statistics:
        - cache_count: 缓存的 m3u8 数量（最多扫描100个）
        - cache_details: 最多显示前20个缓存的详细 TTL 信息
        - max_displayed: 详细信息显示的最大数量
    """
    try:
        redis_client = redis_service.get_client()
        
        # 使用 SCAN 获取所有 m3u8 缓存的 keys（更高效，不会阻塞 Redis）
        cache_keys = []
        cursor = 0
        pattern = f"{M3U8_CONTENT_CACHE_PREFIX}*"
        max_keys = 100
        
        while True:
            cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
            # 限制最多获取 max_keys 个 keys
            remaining = max_keys - len(cache_keys)
            if remaining > 0:
                cache_keys.extend(keys[:remaining])
            if cursor == 0 or len(cache_keys) >= max_keys:
                break
        
        # 获取每个缓存 key 的 TTL 信息（最多显示前20个）
        cache_details = []
        max_displayed = 20
        for key in cache_keys[:max_displayed]:
            try:
                ttl = await redis_client.ttl(key)
                # 从 key 中提取路径哈希
                key_str = key if isinstance(key, str) else key.decode('utf-8')
                path_hash = key_str.replace(M3U8_CONTENT_CACHE_PREFIX, "")
                cache_details.append({
                    "key_hash": path_hash,
                    "ttl": ttl
                })
            except Exception as ttl_error:
                logger.warning(f"获取缓存 key TTL 失败: {key}, error: {str(ttl_error)}")
                continue
        
        return {
            "status": "ok",
            "cache_count": len(cache_keys),
            "cache_details": cache_details,
            "max_displayed": max_displayed,
            "timestamp": int(time.time())
        }
        
    except Exception as e:
        logger.error(f"获取 m3u8 缓存统计失败: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "cache_count": 0,
            "cache_details": [],
            "timestamp": int(time.time())
        }
