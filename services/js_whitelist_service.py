"""
JS白名单追踪服务
JavaScript whitelist tracking service
"""
import json
import hashlib
import time
import logging
from typing import Dict, Any, Optional, Tuple

from services.redis_service import redis_service
from models.config import config
from utils.helpers import validate_token, extract_match_key

logger = logging.getLogger(__name__)


async def add_js_whitelist(
    uid: str,
    js_path: str,
    target_client_ip: str,
    user_agent: str
) -> Dict[str, Any]:
    """
    添加JS文件访问到白名单
    
    支持两种模式:
    1. 指定路径 - js_path为具体路径，使用match_key匹配（提取日期后的文件夹）
    2. 通配符模式 - js_path为空字符串，允许该IP+UA访问所有静态文件
    
    每个UID最多保留3个目录（match_key），新的替换旧的（FIFO）
    
    Args:
        uid: 用户ID
        js_path: JS文件路径（可以为空字符串表示通配符）
        target_client_ip: 客户端IP
        user_agent: User-Agent字符串
    
    Returns:
        Result dictionary with success/error information
    """
    if not config.ENABLE_JS_WHITELIST_TRACKER:
        return {
            "success": False,
            "error": "JS whitelist tracker is disabled"
        }
    
    redis_client = redis_service.get_client()
    
    try:
        # 生成UA+IP的hash作为标识
        ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        ip_hash = hashlib.md5(target_client_ip.encode()).hexdigest()[:8]
        
        # 提取match_key用于匹配（如果路径非空）
        match_key = extract_match_key(js_path) if js_path else ""
        
        # Redis key格式改为: js_wl_frontend:{uid}:{match_key_hash}:{ua_hash}:{ip_hash}
        # 使用 js_wl_frontend 前缀区分前端提交和后端提交
        match_key_hash = hashlib.md5(match_key.encode()).hexdigest()[:12]
        redis_key = f"js_wl_frontend:{uid}:{match_key_hash}:{ua_hash}:{ip_hash}"
        
        current_time = int(time.time())
        
        # 构建白名单数据
        whitelist_data = {
            "uid": uid,
            "js_path": js_path,
            "match_key": match_key,  # 存储提取的match_key
            "client_ip": target_client_ip,
            "user_agent": user_agent,
            "created_at": current_time,
            "expires_at": current_time + config.JS_WHITELIST_TRACKER_TTL,
            "is_wildcard": js_path == ""  # 标记是否为通配符
        }
        
        # 检查该UID现有的目录数量（使用有序集合管理）
        # 使用 Sorted Set 来维护每个UID的目录列表，score为创建时间
        uid_dirs_key = f"js_wl_dirs:{uid}:{ua_hash}:{ip_hash}"
        
        # 获取当前目录数量
        current_count = await redis_client.zcard(uid_dirs_key)
        
        # 如果已经有3个目录且当前match_key不在其中，移除最旧的
        if current_count >= 3:
            # 检查当前match_key是否已存在
            existing_score = await redis_client.zscore(uid_dirs_key, match_key_hash)
            
            if existing_score is None:
                # 新的match_key，需要移除最旧的
                # 获取最旧的目录（score最小的）
                oldest = await redis_client.zrange(uid_dirs_key, 0, 0)
                if oldest:
                    oldest_match_key_hash = oldest[0]
                    # 删除旧目录的白名单记录
                    old_redis_key = f"js_wl_frontend:{uid}:{oldest_match_key_hash}:{ua_hash}:{ip_hash}"
                    await redis_client.delete(old_redis_key)
                    # 从有序集合中移除
                    await redis_client.zrem(uid_dirs_key, oldest_match_key_hash)
                    logger.info(
                        f"🔄 JS白名单: uid={uid}已达3个目录上限，移除最旧目录hash={oldest_match_key_hash}"
                    )
        
        # 添加或更新当前目录到有序集合（使用当前时间作为score）
        await redis_client.zadd(uid_dirs_key, {match_key_hash: current_time})
        # 为有序集合设置过期时间
        await redis_client.expire(uid_dirs_key, config.JS_WHITELIST_TRACKER_TTL)
        
        # 存储白名单数据到Redis
        await redis_client.set(
            redis_key,
            json.dumps(whitelist_data),
            ex=config.JS_WHITELIST_TRACKER_TTL
        )
        
        mode = "通配符(所有静态文件)" if js_path == "" else f"match_key={match_key}, path={js_path}"
        logger.info(
            f"✅ JS白名单添加成功: uid={uid}, {mode}, "
            f"ip={target_client_ip}, ttl={config.JS_WHITELIST_TRACKER_TTL}s"
        )
        
        return {
            "success": True,
            "message": "JS whitelist entry added successfully",
            "data": {
                "uid": uid,
                "js_path": js_path,
                "match_key": match_key,
                "is_wildcard": js_path == "",
                "client_ip": target_client_ip,
                "user_agent": user_agent,  # 返回User-Agent供用户确认
                "ttl": config.JS_WHITELIST_TRACKER_TTL,
                "expires_at": whitelist_data["expires_at"]
            }
        }
        
    except Exception as e:
        logger.error(f"添加JS白名单失败: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to add JS whitelist entry: {str(e)}"
        }


async def check_js_whitelist(
    js_path: str,
    client_ip: str,
    user_agent: str,
    uid: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    检查JS文件访问是否在白名单中
    
    支持两种模式:
    1. Match key匹配 - 使用extract_match_key提取路径中的关键字进行匹配
    2. 通配符模式 - 如果白名单中js_path为空，则允许该IP+UA访问所有静态文件
    
    Args:
        js_path: JS文件路径
        client_ip: 客户端IP
        user_agent: User-Agent字符串
        uid: 用户ID (可选，用于精确匹配)
    
    Returns:
        (is_allowed, whitelist_uid)
    """
    if not config.ENABLE_JS_WHITELIST_TRACKER:
        # 功能未启用时，默认允许访问
        logger.debug("JS whitelist tracker disabled, allowing access")
        return True, None
    
    redis_client = redis_service.get_client()
    
    try:
        # 生成hash标识
        ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        ip_hash = hashlib.md5(client_ip.encode()).hexdigest()[:8]
        
        # 提取match_key用于匹配
        match_key = extract_match_key(js_path)
        match_key_hash = hashlib.md5(match_key.encode()).hexdigest()[:12]
        
        if uid:
            # 如果提供了UID，直接检查特定key（使用match_key）
            # 使用新的key前缀 js_wl_frontend
            redis_key = f"js_wl_frontend:{uid}:{match_key_hash}:{ua_hash}:{ip_hash}"
            whitelist_data = await redis_client.get(redis_key)
            
            if whitelist_data:
                try:
                    data = json.loads(whitelist_data)
                    logger.info(
                        f"✅ JS白名单验证成功: uid={uid}, match_key={match_key}, path={js_path}, "
                        f"ip={client_ip}"
                    )
                    return True, uid
                except json.JSONDecodeError:
                    pass
            
            # 检查是否有通配符白名单（空路径）
            empty_key_hash = hashlib.md5(b"").hexdigest()[:12]
            wildcard_key = f"js_wl_frontend:{uid}:{empty_key_hash}:{ua_hash}:{ip_hash}"
            wildcard_data = await redis_client.get(wildcard_key)
            
            if wildcard_data:
                try:
                    data = json.loads(wildcard_data)
                    logger.info(
                        f"✅ JS白名单验证成功(通配符): uid={uid}, path={js_path}, "
                        f"ip={client_ip}"
                    )
                    return True, uid
                except json.JSONDecodeError:
                    pass
        else:
            # 如果没有提供UID，搜索匹配的key（使用match_key）
            pattern = f"js_wl_frontend:*:{match_key_hash}:{ua_hash}:{ip_hash}"
            keys = await redis_client.keys(pattern)
            
            if keys:
                # 找到匹配的key，获取第一个
                whitelist_data = await redis_client.get(keys[0])
                if whitelist_data:
                    try:
                        data = json.loads(whitelist_data)
                        found_uid = data.get("uid")
                        logger.info(
                            f"✅ JS白名单验证成功: uid={found_uid}, match_key={match_key}, path={js_path}, "
                            f"ip={client_ip}"
                        )
                        return True, found_uid
                    except json.JSONDecodeError:
                        pass
            
            # 检查是否有通配符白名单（空路径）
            empty_key_hash = hashlib.md5(b"").hexdigest()[:12]
            wildcard_pattern = f"js_wl_frontend:*:{empty_key_hash}:{ua_hash}:{ip_hash}"
            wildcard_keys = await redis_client.keys(wildcard_pattern)
            
            if wildcard_keys:
                # 找到通配符白名单
                wildcard_data = await redis_client.get(wildcard_keys[0])
                if wildcard_data:
                    try:
                        data = json.loads(wildcard_data)
                        found_uid = data.get("uid")
                        logger.info(
                            f"✅ JS白名单验证成功(通配符): uid={found_uid}, path={js_path}, "
                            f"ip={client_ip}"
                        )
                        return True, found_uid
                    except json.JSONDecodeError:
                        pass
        
        # 不在这里记录失败日志，由调用方根据上下文记录
        # 这样可以避免在后端验证已通过的情况下产生误导性日志
        return False, None
        
    except Exception as e:
        logger.error(f"检查JS白名单失败: {str(e)}")
        # 发生错误时默认拒绝访问
        return False, None


async def get_js_whitelist_stats(uid: str) -> Dict[str, Any]:
    """
    获取用户的JS白名单统计信息
    
    Args:
        uid: 用户ID
    
    Returns:
        Statistics dictionary
    """
    if not config.ENABLE_JS_WHITELIST_TRACKER:
        return {
            "enabled": False,
            "message": "JS whitelist tracker is disabled"
        }
    
    redis_client = redis_service.get_client()
    
    try:
        # 查找该用户的所有JS白名单记录（使用新的key前缀）
        pattern = f"js_wl_frontend:{uid}:*"
        keys = await redis_client.keys(pattern)
        
        entries = []
        for key in keys:
            data_str = await redis_client.get(key)
            if data_str:
                try:
                    data = json.loads(data_str)
                    ttl = await redis_client.ttl(key)
                    data["remaining_ttl"] = ttl
                    entries.append(data)
                except json.JSONDecodeError:
                    continue
        
        return {
            "enabled": True,
            "uid": uid,
            "total_entries": len(entries),
            "entries": entries,
            "ttl_config": config.JS_WHITELIST_TRACKER_TTL
        }
        
    except Exception as e:
        logger.error(f"获取JS白名单统计失败: {str(e)}")
        return {
            "enabled": True,
            "error": str(e)
        }
