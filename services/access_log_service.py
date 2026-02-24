"""
Access Log Service
记录和管理访问日志到 Redis，用于监控面板展示
"""
import json
import time
import logging
from typing import Optional, List, Dict, Any

from services.redis_service import redis_service

logger = logging.getLogger(__name__)

# Redis keys for access logs
ACCESS_LOG_DENIED_KEY = "access_log:denied"
ACCESS_LOG_RECENT_KEY = "access_log:recent"

# Maximum number of records to keep
MAX_LOG_RECORDS = 100


async def log_access(
    uid: Optional[str],
    ip: str,
    user_agent: str,
    path: str,
    allowed: bool,
    reason: Optional[str] = None
):
    """
    记录访问日志到 Redis
    
    Args:
        uid: 用户ID（可为空）
        ip: 客户端IP地址
        user_agent: User-Agent
        path: 访问路径
        allowed: 是否允许访问
        reason: 拒绝原因（如果被拒绝）
    """
    try:
        redis_client = redis_service.get_client()
        
        # 创建访问记录
        access_record = {
            "uid": uid or "unknown",
            "ip": ip,
            "ua": user_agent,
            "path": path,
            "timestamp": int(time.time()),
            "allowed": allowed
        }
        
        if not allowed and reason:
            access_record["reason"] = reason
        
        # 将记录序列化为 JSON
        record_json = json.dumps(access_record)
        
        # 选择正确的列表
        key = ACCESS_LOG_RECENT_KEY if allowed else ACCESS_LOG_DENIED_KEY
        
        # 使用 LPUSH 添加到列表头部（最新的在前面）
        await redis_client.lpush(key, record_json)
        
        # 使用 LTRIM 保持列表长度在 MAX_LOG_RECORDS 以内
        await redis_client.ltrim(key, 0, MAX_LOG_RECORDS - 1)
        
        # 设置过期时间（7天）
        await redis_client.expire(key, 7 * 24 * 60 * 60)
        
    except Exception as e:
        # 记录日志失败不应该影响正常请求
        logger.error(f"记录访问日志失败: {str(e)}")


async def get_denied_access_logs(limit: int = 100) -> List[Dict[str, Any]]:
    """
    获取被拒绝的访问日志
    
    Args:
        limit: 返回的最大记录数
        
    Returns:
        List of access log records
    """
    try:
        redis_client = redis_service.get_client()
        
        # 获取列表中的记录
        records = await redis_client.lrange(ACCESS_LOG_DENIED_KEY, 0, limit - 1)
        
        # 解析 JSON 记录
        access_logs = []
        for record in records:
            try:
                access_logs.append(json.loads(record))
            except json.JSONDecodeError:
                logger.error(f"解析访问记录失败: {record}")
                continue
        
        return access_logs
        
    except Exception as e:
        logger.error(f"获取拒绝访问日志失败: {str(e)}")
        return []


async def get_recent_access_logs(limit: int = 100) -> List[Dict[str, Any]]:
    """
    获取最近成功的访问日志
    
    Args:
        limit: 返回的最大记录数
        
    Returns:
        List of access log records
    """
    try:
        redis_client = redis_service.get_client()
        
        # 获取列表中的记录
        records = await redis_client.lrange(ACCESS_LOG_RECENT_KEY, 0, limit - 1)
        
        # 解析 JSON 记录
        access_logs = []
        for record in records:
            try:
                access_logs.append(json.loads(record))
            except json.JSONDecodeError:
                logger.error(f"解析访问记录失败: {record}")
                continue
        
        return access_logs
        
    except Exception as e:
        logger.error(f"获取最近访问日志失败: {str(e)}")
        return []


async def get_access_logs_summary() -> Dict[str, Any]:
    """
    获取访问日志摘要统计
    
    Returns:
        Summary statistics
    """
    try:
        redis_client = redis_service.get_client()
        
        denied_count = await redis_client.llen(ACCESS_LOG_DENIED_KEY)
        recent_count = await redis_client.llen(ACCESS_LOG_RECENT_KEY)
        
        return {
            "denied_count": denied_count,
            "recent_count": recent_count,
            "max_records": MAX_LOG_RECORDS
        }
        
    except Exception as e:
        logger.error(f"获取访问日志摘要失败: {str(e)}")
        return {
            "denied_count": 0,
            "recent_count": 0,
            "max_records": MAX_LOG_RECORDS
        }
