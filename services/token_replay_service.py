"""
Token 防重放服务
实现基于 Redis 的 token 单次/限次使用保护

功能说明：
- 对于包含 token 参数的请求（如 /index.m3u8?uid=315&expires=1769692849&token=xxx）
- 使用 Redis 记录 token 使用次数
- 支持配置最大使用次数（默认为 1，即单次使用）
- 支持配置 token 记录的 TTL（过期后自动清理）
- 防止恶意重放攻击
- 记录重放日志供监控面板展示

配置项（在 models/config.py 中）：
- TOKEN_REPLAY_ENABLED: 是否启用 token 防重放保护
- TOKEN_REPLAY_MAX_USES: 每个 token 最大使用次数
- TOKEN_REPLAY_TTL: token 记录在 Redis 中的 TTL（秒）
"""
import asyncio
import json
import logging
import hashlib
import time
from typing import Tuple, Dict, Any, Optional, List

from services.redis_service import redis_service

logger = logging.getLogger(__name__)

# Redis key for replay logs
REPLAY_LOG_KEY = "token_replay:logs"
MAX_REPLAY_LOG_RECORDS = 300

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
            # Re-raise exception if any to log it
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


async def check_token_replay(
    token: str,
    uid: str,
    path: str,
    max_uses: int,
    ttl: int,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    full_url: Optional[str] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    检查 token 是否已被重放使用
    
    Args:
        token: 请求中的 token 参数
        uid: 用户 ID
        path: 请求路径
        max_uses: 最大允许使用次数
        ttl: Redis 记录的 TTL（秒）
        client_ip: 客户端 IP（可选，用于日志记录）
        user_agent: User-Agent（可选，用于日志记录）
        full_url: 完整 URL（可选，包含查询参数，用于日志记录）
    
    Returns:
        Tuple[bool, Dict[str, Any]]: 
            - bool: True 表示允许访问，False 表示被拒绝（重放攻击）
            - Dict: 包含详细信息的字典
    """
    redis_client = redis_service.get_client()
    
    try:
        # 生成 Redis key
        # 使用 token + uid + path 的组合作为唯一标识
        # 这样同一个 token 在不同路径下的使用会被分别计数
        key_content = f"{token}:{uid}:{path}"
        token_hash = hashlib.sha256(key_content.encode()).hexdigest()
        redis_key = f"token_replay:{token_hash}"
        
        # 使用 Redis INCR 原子操作递增计数器
        current_count = await redis_client.incr(redis_key)
        
        # 如果是第一次使用，设置 TTL
        # 注意：INCR 和 EXPIRE 不是原子操作，但实际影响很小：
        # 1. 如果 EXPIRE 失败，key 不会自动过期，但最终会被后续请求或人工清理
        # 2. Redis 的 INCR 创建的 key 如果没有 TTL，可以通过 Redis 内存策略清理
        if current_count == 1:
            await redis_client.expire(redis_key, ttl)
            logger.info(
                f"Token 首次使用: uid={uid}, path={path}, "
                f"ip={client_ip or 'unknown'}, max_uses={max_uses}, ttl={ttl}s"
            )
            
            return True, {
                "allowed": True,
                "current_count": current_count,
                "max_uses": max_uses,
                "remaining_uses": max_uses - current_count,
                "is_first_use": True,
                "ttl": ttl
            }
        
        # 检查是否超过最大使用次数
        if current_count <= max_uses:
            remaining_ttl = await redis_client.ttl(redis_key)
            
            # 安全检查：如果 key 存在但没有 TTL（值为-1），说明之前的 EXPIRE 可能失败了
            # 这种情况下重新设置 TTL
            if remaining_ttl == -1:
                await redis_client.expire(redis_key, ttl)
                remaining_ttl = ttl
            
            logger.info(
                f"Token 使用允许: uid={uid}, count={current_count}/{max_uses}, "
                f"ip={client_ip or 'unknown'}"
            )
            
            # 仅当不是首次使用时记录重放事件（首次使用不算重放）
            # 使用 fire-and-forget 模式避免阻塞主请求
            if current_count > 1:
                _schedule_background_task(log_replay_event(
                    uid=uid,
                    path=path,
                    client_ip=client_ip or "unknown",
                    current_count=current_count,
                    max_uses=max_uses,
                    is_blocked=False,
                    user_agent=user_agent,
                    full_url=full_url
                ))
            
            return True, {
                "allowed": True,
                "current_count": current_count,
                "max_uses": max_uses,
                "remaining_uses": max_uses - current_count,
                "is_first_use": False,
                "remaining_ttl": remaining_ttl
            }
        else:
            remaining_ttl = await redis_client.ttl(redis_key)
            logger.warning(
                f"Token 重放检测: uid={uid}, count={current_count}/{max_uses}, "
                f"ip={client_ip or 'unknown'}, path={path}"
            )
            
            # 记录重放事件（被阻止的情况）- 使用 fire-and-forget 模式
            _schedule_background_task(log_replay_event(
                uid=uid,
                path=path,
                client_ip=client_ip or "unknown",
                current_count=current_count,
                max_uses=max_uses,
                is_blocked=True,
                user_agent=user_agent,
                full_url=full_url
            ))
            
            return False, {
                "allowed": False,
                "current_count": current_count,
                "max_uses": max_uses,
                "remaining_uses": 0,
                "is_first_use": False,
                "remaining_ttl": remaining_ttl,
                "exceeded": True,
                "reason": "Token replay detected: maximum usage count exceeded"
            }
            
    except Exception as e:
        logger.error(f"检查 token 重放失败: {str(e)}")
        # 出错时默认允许访问，避免因 Redis 故障导致服务不可用
        return True, {
            "allowed": True,
            "error": str(e),
            "fallback": True
        }


async def get_token_usage_info(
    token: str,
    uid: str,
    path: str
) -> Dict[str, Any]:
    """
    获取 token 的使用信息（不增加计数）
    
    Args:
        token: 请求中的 token 参数
        uid: 用户 ID
        path: 请求路径
    
    Returns:
        Dict: 包含 token 使用信息的字典
    """
    redis_client = redis_service.get_client()
    
    try:
        key_content = f"{token}:{uid}:{path}"
        token_hash = hashlib.sha256(key_content.encode()).hexdigest()
        redis_key = f"token_replay:{token_hash}"
        
        # 获取当前计数（不增加）
        current_count = await redis_client.get(redis_key)
        
        if current_count is None:
            return {
                "exists": False,
                "current_count": 0,
                "message": "Token has not been used yet"
            }
        
        remaining_ttl = await redis_client.ttl(redis_key)
        
        return {
            "exists": True,
            "current_count": int(current_count),
            "remaining_ttl": remaining_ttl
        }
        
    except Exception as e:
        logger.error(f"获取 token 使用信息失败: {str(e)}")
        return {
            "error": str(e)
        }


async def invalidate_token(
    token: str,
    uid: str,
    path: str
) -> bool:
    """
    手动使 token 失效（删除 Redis 记录）
    
    Args:
        token: 请求中的 token 参数
        uid: 用户 ID
        path: 请求路径
    
    Returns:
        bool: 是否成功删除
    """
    redis_client = redis_service.get_client()
    
    try:
        key_content = f"{token}:{uid}:{path}"
        token_hash = hashlib.sha256(key_content.encode()).hexdigest()
        redis_key = f"token_replay:{token_hash}"
        
        deleted = await redis_client.delete(redis_key)
        
        if deleted:
            logger.info(f"Token 已手动失效: uid={uid}, path={path}")
            return True
        else:
            logger.info(f"Token 不存在或已过期: uid={uid}, path={path}")
            return False
            
    except Exception as e:
        logger.error(f"使 token 失效失败: {str(e)}")
        return False


async def log_replay_event(
    uid: str,
    path: str,
    client_ip: str,
    current_count: int,
    max_uses: int,
    is_blocked: bool,
    user_agent: Optional[str] = None,
    full_url: Optional[str] = None
) -> None:
    """
    记录重放事件到 Redis 日志列表
    
    Args:
        uid: 用户 ID
        path: 请求路径
        client_ip: 客户端 IP
        current_count: 当前使用次数
        max_uses: 最大允许使用次数
        is_blocked: 是否被阻止
        user_agent: User-Agent（可选）
        full_url: 完整 URL（包含查询参数，可选）
    """
    try:
        redis_client = redis_service.get_client()
        
        # 创建日志记录
        log_record = {
            "uid": uid,
            "path": path,
            "full_url": full_url[:500] if full_url else path,  # 完整 URL，截断过长的
            "ip": client_ip,
            "ua": user_agent[:200] if user_agent else None,  # 截断过长的 UA（增加到200字符）
            "count": current_count,
            "max_uses": max_uses,
            "blocked": is_blocked,
            "timestamp": int(time.time())
        }
        
        # 序列化为 JSON
        record_json = json.dumps(log_record)
        
        # 使用 pipeline 批量执行所有操作（优化：减少网络往返）
        pipe = redis_client.pipeline()
        pipe.lpush(REPLAY_LOG_KEY, record_json)
        pipe.ltrim(REPLAY_LOG_KEY, 0, MAX_REPLAY_LOG_RECORDS - 1)
        pipe.expire(REPLAY_LOG_KEY, 7 * 24 * 60 * 60)
        await pipe.execute()
        
    except Exception as e:
        # 记录日志失败不应该影响正常请求
        logger.error(f"记录重放事件失败: {str(e)}")


async def get_replay_logs(limit: int = 300) -> List[Dict[str, Any]]:
    """
    获取重放日志记录
    
    Args:
        limit: 返回的最大记录数（最多300条）
        
    Returns:
        List of replay log records
    """
    try:
        redis_client = redis_service.get_client()
        
        # 确保 limit 不超过最大值
        limit = min(limit, MAX_REPLAY_LOG_RECORDS)
        
        # 获取列表中的记录
        records = await redis_client.lrange(REPLAY_LOG_KEY, 0, limit - 1)
        
        # 解析 JSON 记录
        replay_logs = []
        for record in records:
            try:
                replay_logs.append(json.loads(record))
            except json.JSONDecodeError:
                logger.error(f"解析重放日志记录失败: {record}")
                continue
        
        return replay_logs
        
    except Exception as e:
        logger.error(f"获取重放日志失败: {str(e)}")
        return []


async def get_replay_logs_summary() -> Dict[str, Any]:
    """
    获取重放日志摘要统计
    
    Returns:
        Summary statistics
    """
    try:
        redis_client = redis_service.get_client()
        
        total_count = await redis_client.llen(REPLAY_LOG_KEY)
        
        # 获取最近的一些记录来计算被阻止的数量
        recent_records = await redis_client.lrange(REPLAY_LOG_KEY, 0, 99)
        blocked_count = 0
        for record in recent_records:
            try:
                data = json.loads(record)
                if data.get("blocked"):
                    blocked_count += 1
            except json.JSONDecodeError:
                continue
        
        return {
            "total_count": total_count,
            "recent_blocked_count": blocked_count,
            "max_records": MAX_REPLAY_LOG_RECORDS
        }
        
    except Exception as e:
        logger.error(f"获取重放日志摘要失败: {str(e)}")
        return {
            "total_count": 0,
            "recent_blocked_count": 0,
            "max_records": MAX_REPLAY_LOG_RECORDS
        }
