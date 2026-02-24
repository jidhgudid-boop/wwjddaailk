"""
会话管理服务
Session management for user authentication and authorization
"""
import json
import uuid
import hashlib
import time
import logging
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime

from services.redis_service import redis_service
from models.config import config
from utils.helpers import extract_match_key

logger = logging.getLogger(__name__)


async def batch_redis_operations(redis_client, operations: List[Tuple]) -> List[Any]:
    """批量执行Redis操作"""
    return await redis_service.batch_operations(operations, use_pipeline=config.ENABLE_REDIS_PIPELINE)


async def get_or_validate_session_by_ip_ua(
    uid: Optional[str],
    client_ip: str,
    user_agent: str,
    path: str
) -> Tuple[Optional[str], bool, Optional[str]]:
    """
    通过 IP + UA + key_path 获取或验证会话
    
    Returns:
        (session_id, is_new_session, effective_uid)
    """
    redis_client = redis_service.get_client()
    try:
        key_path = extract_match_key(path)
        if not key_path:
            logger.debug(f"无效的 key_path 提取: path={path}")
            return None, False, None
        
        ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        effective_uid = uid
        
        # 如果提供了 UID，尝试精确匹配
        if uid:
            session_key = f"ip_ua_session:{client_ip}:{ua_hash}:{uid}:{key_path}"
            existing_session_id = await redis_client.get(session_key)
            
            if existing_session_id:
                session_data = await validate_session_internal(redis_client, existing_session_id, client_ip, user_agent)
                if session_data and session_data.get("uid") == uid and session_data.get("key_path") == key_path:
                    if await extend_session(redis_client, existing_session_id, session_data):
                        logger.debug(f"复用 IP+UA+UID+key_path 会话: {existing_session_id}, ip={client_ip}, uid={uid}")
                        return existing_session_id, False, uid
        
        # 后备：查找匹配 IP+UA+key_path 的会话（用于 .ts 和 enc.key）
        session_key_pattern = f"ip_ua_session:{client_ip}:{ua_hash}:*:{key_path}"
        session_keys = await redis_client.keys(session_key_pattern)
        
        if session_keys:
            latest_session_id = None
            latest_session_data = None
            latest_timestamp = 0
            
            for session_key in session_keys:
                session_id = await redis_client.get(session_key)
                if session_id:
                    session_data = await validate_session_internal(redis_client, session_id, client_ip, user_agent)
                    if session_data and session_data.get("key_path") == key_path:
                        last_activity = session_data.get("last_activity", 0)
                        if last_activity > latest_timestamp:
                            latest_timestamp = last_activity
                            latest_session_id = session_id
                            latest_session_data = session_data
            
            if latest_session_id:
                effective_uid = latest_session_data.get("uid")
                if await extend_session(redis_client, latest_session_id, latest_session_data):
                    logger.debug(f"复用 IP+UA+key_path 会话: {latest_session_id}, ip={client_ip}, uid={effective_uid}")
                    return latest_session_id, False, effective_uid
        
        # 仅当提供了 UID 时创建新会话
        if not uid:
            logger.debug(f"未提供 UID 且未找到匹配会话: IP={client_ip}, UA hash={ua_hash}, key_path={key_path}")
            return None, False, None
        
        # 创建新会话
        session_id = str(uuid.uuid4())
        now = datetime.now()
        session_data = {
            "uid": uid,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "path": path,
            "key_path": key_path,
            "created_at": int(now.timestamp()),
            "last_activity": int(now.timestamp()),
            "access_count": 1,
            "session_type": "ip_ua_key_path_based"
        }
        
        session_key = f"ip_ua_session:{client_ip}:{ua_hash}:{uid}:{key_path}"
        operations = [
            ('set', f"session:{session_id}", json.dumps(session_data), 'EX', config.SESSION_TTL),
            ('set', session_key, session_id, 'EX', config.SESSION_TTL)
        ]
        
        results = await batch_redis_operations(redis_client, operations)
        
        if results[0] is not None:
            logger.info(f"创建 IP+UA+key_path 会话: session_id={session_id}, uid={uid}, ip={client_ip}, key_path={key_path}")
            return session_id, True, uid
        else:
            logger.error(f"会话创建失败: {session_id}")
            return None, False, None
        
    except Exception as e:
        logger.error(f"IP+UA+key_path 会话操作失败: path={path}, error={str(e)}")
        return None, False, None


async def validate_session_internal(
    redis_client,
    session_id: str,
    client_ip: str,
    user_agent: str
) -> Optional[dict]:
    """内部session验证函数，复用Redis连接"""
    try:
        redis_key = f"session:{session_id}"
        session_data = await redis_client.get(redis_key)
        if not session_data:
            logger.debug(f"Session not found: {session_id}")
            return None
        
        session_data = json.loads(session_data)
        
        # 验证IP和UA
        if session_data["client_ip"] != client_ip:
            logger.warning(f"Session IP mismatch: stored={session_data['client_ip']}, request={client_ip}")
            return None
        
        if session_data["user_agent"] != user_agent:
            logger.warning(f"Session User-Agent mismatch: session_id={session_id}")
            return None
        
        logger.debug(f"Session validated: {session_id}, uid={session_data['uid']}")
        return session_data
        
    except Exception as e:
        logger.error(f"Session validation error: {str(e)}")
        return None


async def extend_session(redis_client, session_id: str, session_data: dict) -> bool:
    """延长session有效期并更新活动时间"""
    try:
        now = datetime.now()
        session_data["last_activity"] = int(now.timestamp())
        session_data["access_count"] = session_data.get("access_count", 0) + 1
        
        operations = [
            ('set', f"session:{session_id}", json.dumps(session_data), 'EX', config.SESSION_TTL),
            ('expire', f"user_active_session:{session_data['uid']}:{session_data['client_ip']}", config.USER_SESSION_TTL)
        ]
        
        results = await batch_redis_operations(redis_client, operations)
        
        logger.debug(f"延长session有效期: {session_id}, ttl={config.SESSION_TTL}s")
        return results[0] is not None
    except Exception as e:
        logger.error(f"延长session失败: {str(e)}")
        return False


async def validate_session(session_id: str, client_ip: str, user_agent: str) -> Optional[dict]:
    """验证session并返回session数据"""
    redis_client = redis_service.get_client()
    return await validate_session_internal(redis_client, session_id, client_ip, user_agent)
