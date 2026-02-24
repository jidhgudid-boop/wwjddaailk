"""
认证服务
Authentication and authorization services including HMAC validation and IP whitelist
"""
import json
import hashlib
import time
import logging
from typing import Tuple, Optional, Dict, Any

from services.redis_service import redis_service
from models.config import config
from utils.helpers import validate_token, extract_match_key
from utils.cidr_matcher import CIDRMatcher
from utils.browser_detector import BrowserDetector

logger = logging.getLogger(__name__)


def is_ip_in_fixed_whitelist(client_ip: str) -> bool:
    """
    检查IP是否在固定白名单中
    支持单个IP和CIDR格式
    
    Args:
        client_ip: 客户端IP地址
    
    Returns:
        bool: 如果IP在固定白名单中返回True，否则返回False
    """
    if not config.FIXED_IP_WHITELIST:
        return False
    
    try:
        # 使用CIDR匹配器检查IP是否匹配白名单中的任何模式
        is_match, matched_pattern = CIDRMatcher.match_ip_against_patterns(
            client_ip, 
            config.FIXED_IP_WHITELIST
        )
        if is_match:
            logger.info(f"✅ 固定白名单验证成功: IP={client_ip} 匹配模式={matched_pattern}")
            return True
        return False
    except Exception as e:
        logger.error(f"检查固定白名单失败: IP={client_ip}, error={str(e)}")
        return False


async def check_ip_key_path(client_ip: str, path: str, user_agent: str) -> Tuple[bool, Optional[str]]:
    """
    检查IP是否有权访问指定路径（使用CIDR白名单）
    
    Returns:
        (is_allowed, whitelist_uid)
    """
    # 首先检查固定白名单 - 如果在固定白名单中，直接放行
    if is_ip_in_fixed_whitelist(client_ip):
        logger.info(f"🔓 固定白名单放行: IP={client_ip}, path={path}")
        return True, "fixed_whitelist"
    
    redis_client = redis_service.get_client()
    try:
        # 检查是否为静态文件且启用了IP-only验证
        is_static_file = path.lower().endswith(config.STATIC_FILE_EXTENSIONS)
        skip_path_check = is_static_file and config.ENABLE_STATIC_FILE_IP_ONLY_CHECK
        
        if skip_path_check:
            logger.info(f"静态文件IP-only验证模式: path={path}")
            
            # 首先检查独立的静态文件白名单
            is_static_allowed, static_uid = await check_static_file_access(client_ip, user_agent)
            if is_static_allowed:
                logger.info(f"✅ 静态文件独立白名单验证成功: IP={client_ip}, uid={static_uid}, path={path}")
                return True, static_uid
        
        requested_key_path = extract_match_key(path)
        if not requested_key_path and not skip_path_check:
            logger.debug(f"无效的 key_path: path={path}")
            return False, None
        
        ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        
        # 统一CIDR匹配方法：查找所有匹配的CIDR模式
        cidr_pattern = f"ip_cidr_access:*:{ua_hash}"
        cidr_keys = await redis_client.keys(cidr_pattern)
        
        stored_key_path = None
        stored_uid = None
        
        for cidr_key in cidr_keys:
            cidr_data = await redis_client.get(cidr_key)
            if cidr_data:
                try:
                    data = json.loads(cidr_data)
                    ip_patterns = data.get("ip_patterns", [])
                    
                    # 使用CIDR匹配检查IP
                    is_match, matched_pattern = CIDRMatcher.match_ip_against_patterns(client_ip, ip_patterns)
                    if is_match:
                        stored_uid = data.get("uid")
                        
                        # 对于静态文件且启用IP-only检查，只验证IP+UA，跳过路径检查
                        if skip_path_check:
                            logger.info(f"✅ 静态文件IP+UA验证成功（路径白名单）: IP={client_ip} 匹配模式={matched_pattern}, uid={stored_uid}, path={path}")
                            return True, stored_uid
                        
                        # 正常模式：检查多路径支持
                        paths = data.get("paths", [])
                        if paths:
                            # 检查请求的路径是否在存储的路径列表中
                            for path_info in paths:
                                stored_path = path_info.get("key_path")
                                if stored_path and stored_path == requested_key_path:
                                    stored_key_path = stored_path
                                    logger.info(f"✅ CIDR匹配成功: IP={client_ip} 匹配模式={matched_pattern}, 路径={stored_path}")
                                    break
                        else:
                            # 向后兼容：使用单一key_path
                            if data.get("key_path", "") == requested_key_path:
                                stored_key_path = data.get("key_path")
                                logger.info(f"✅ CIDR匹配成功: IP={client_ip} 匹配模式={matched_pattern}, 路径={stored_key_path}")
                        if stored_key_path:
                            break
                except json.JSONDecodeError:
                    continue
        
        if not stored_key_path and not (skip_path_check and stored_uid):
            # 判断是否为静态文件（可能由JS白名单验证）
            is_potential_js_whitelist = (
                is_static_file or 
                path.lower().endswith(('.m3u8', '.ts', 'enc.key', '.jpg', '.png', '.gif', '.svg', '.ico'))
            )
            
            # 如果是静态文件且启用了JS白名单，使用DEBUG级别（避免噪音）
            # 因为后续可能通过JS白名单验证
            if is_potential_js_whitelist and config.ENABLE_JS_WHITELIST_TRACKER:
                logger.debug(
                    f"后端IP验证未通过（将尝试JS白名单）: IP={client_ip}, "
                    f"UA hash={ua_hash}, requested_key={requested_key_path}"
                )
            else:
                logger.warning(
                    f"❌ IP访问被拒绝: IP={client_ip} 未找到匹配的CIDR模式, "
                    f"UA hash={ua_hash}, requested_key={requested_key_path}"
                )
            return False, None
        
        # 如果是静态文件IP-only模式，前面已经返回了
        # 这里处理正常模式的路径检查
        if stored_key_path:
            # 检查访问权限（使用原始的substring匹配逻辑）
            if stored_key_path.lower() not in path.lower():
                logger.warning(f"❌ 访问被拒绝: IP={client_ip}, path={path}, requested_key={requested_key_path}, allowed_key={stored_key_path}")
                return False, stored_uid
            
            logger.info(f"✅ 访问允许: IP={client_ip}, path={path}, key_path={stored_key_path}, uid={stored_uid}")
            return True, stored_uid
        
        return False, None
        
    except Exception as e:
        logger.error(f"检查 key_path 失败: IP={client_ip}, path={path}, error={str(e)}")
        return False, None


async def check_m3u8_access_count_adaptive(
    uid: str,
    full_url: str,
    client_ip: str,
    user_agent: str
) -> Tuple[bool, Dict[str, Any]]:
    """
    基于浏览器类型的自适应 M3U8 访问次数检查
    
    Returns:
        (is_allowed, access_info)
    """
    redis_client = redis_service.get_client()
    
    try:
        # 检测浏览器类型
        browser_type, browser_name, suggested_max_count = BrowserDetector.detect_browser_type(user_agent)
        
        # 获取配置的访问次数限制
        if config.ENABLE_BROWSER_ADAPTIVE_ACCESS:
            access_limits = config.M3U8_ACCESS_LIMITS.get(browser_type, {})
            max_access_count = access_limits.get(browser_name, access_limits.get('default', suggested_max_count))
            access_window_ttl = config.M3U8_ACCESS_WINDOW_TTL.get(browser_type, 60)
        else:
            # 向后兼容：使用原始配置
            max_access_count = config.M3U8_DEFAULT_MAX_ACCESS_COUNT
            access_window_ttl = config.M3U8_SINGLE_USE_TTL if hasattr(config, 'M3U8_SINGLE_USE_TTL') else 60
        
        # 生成请求标识
        request_identifier = f"{uid}:{full_url}:{client_ip}"
        request_hash = hashlib.sha256(request_identifier.encode()).hexdigest()
        redis_key = f"m3u8_access_count_v2:{request_hash}"
        
        logger.info(f"M3U8访问检查: uid={uid}, browser_type={browser_type}, browser_name={browser_name}, "
                   f"max_count={max_access_count}, window_ttl={access_window_ttl}s")
        
        # 使用Redis原子操作递增计数器
        current_count = await redis_client.incr(redis_key)
        
        # 如果是第一次访问，设置过期时间
        if current_count == 1:
            await redis_client.expire(redis_key, access_window_ttl)
            logger.info(f"M3U8首次访问: uid={uid}, browser={browser_name}")
            
            access_info = {
                "browser_type": browser_type,
                "browser_name": browser_name,
                "current_count": current_count,
                "max_count": max_access_count,
                "window_ttl": access_window_ttl,
                "remaining_count": max_access_count - current_count,
                "is_first_access": True
            }
            return True, access_info
        
        # 检查是否超过最大访问次数
        if current_count <= max_access_count:
            remaining_ttl = await redis_client.ttl(redis_key)
            logger.info(f"M3U8访问允许: uid={uid}, browser={browser_name}, count={current_count}/{max_access_count}")
            
            access_info = {
                "browser_type": browser_type,
                "browser_name": browser_name,
                "current_count": current_count,
                "max_count": max_access_count,
                "remaining_ttl": remaining_ttl,
                "remaining_count": max_access_count - current_count,
                "is_first_access": False
            }
            return True, access_info
        else:
            remaining_ttl = await redis_client.ttl(redis_key)
            logger.warning(f"M3U8访问次数超限: uid={uid}, browser={browser_name}, count={current_count}/{max_access_count}")
            
            access_info = {
                "browser_type": browser_type,
                "browser_name": browser_name,
                "current_count": current_count,
                "max_count": max_access_count,
                "remaining_ttl": remaining_ttl,
                "remaining_count": 0,
                "is_first_access": False,
                "exceeded": True
            }
            return False, access_info
            
    except Exception as e:
        logger.error(f"检查M3U8访问次数失败: {str(e)}")
        access_info = {
            "browser_type": "unknown",
            "browser_name": "unknown",
            "error": str(e)
        }
        return False, access_info


async def check_m3u8_access_count(uid: str, full_url: str, client_ip: str, user_agent: str) -> bool:
    """向后兼容的 M3U8 访问检查函数"""
    is_allowed, _ = await check_m3u8_access_count_adaptive(uid, full_url, client_ip, user_agent)
    return is_allowed


async def add_ip_to_whitelist(
    uid: str,
    path: str,
    target_client_ip: str,
    user_agent: str
) -> Dict[str, Any]:
    """
    添加IP到白名单
    
    Returns:
        Result dictionary with success/error information
    """
    redis_client = redis_service.get_client()
    
    try:
        # Extract key path
        key_path = extract_match_key(path)
        if not key_path:
            return {
                "success": False,
                "error": "Invalid path format"
            }
        
        # 标准化IP地址（自动转换为/24子网）
        if CIDRMatcher.is_valid_ip(target_client_ip) or CIDRMatcher.is_cidr_notation(target_client_ip):
            normalized_pattern = CIDRMatcher.normalize_cidr(target_client_ip)
            logger.info(f"已标准化IP模式: {target_client_ip} -> {normalized_pattern}")
        else:
            return {
                "success": False,
                "error": f"Invalid IP address or CIDR: {target_client_ip}"
            }
        
        # Store in Redis using unified CIDR approach
        ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        current_time = int(time.time())
        
        # 统一使用CIDR键格式存储所有IP
        redis_key = f"ip_cidr_access:{normalized_pattern.replace('/', '_')}:{ua_hash}"
        
        # 构建数据结构，支持多路径存储
        whitelist_data = {
            "uid": uid,
            "key_path": key_path,
            "paths": [{"key_path": key_path, "created_at": current_time}],
            "ip_patterns": [normalized_pattern],
            "user_agent": user_agent,
            "created_at": current_time
        }
        
        # 检查是否已存在，如果存在则合并路径
        existing_data_str = await redis_client.get(redis_key)
        merged_count = 0
        new_count = 1
        
        if existing_data_str:
            try:
                existing_data = json.loads(existing_data_str)
                existing_paths = existing_data.get("paths", [])
                
                # 检查新路径是否已存在
                path_exists = any(p.get("key_path") == key_path for p in existing_paths)
                
                if not path_exists:
                    # 添加新路径
                    existing_paths.append({"key_path": key_path, "created_at": current_time})
                    
                    # 保持最多配置的路径数
                    if len(existing_paths) > config.MAX_PATHS_PER_CIDR:
                        existing_paths.sort(key=lambda x: x.get("created_at", 0))
                        # 获取被移除的旧路径
                        removed_paths = existing_paths[:-config.MAX_PATHS_PER_CIDR]
                        existing_paths = existing_paths[-config.MAX_PATHS_PER_CIDR:]
                        
                        # 清理旧路径的m3u8访问计数器
                        for old_path in removed_paths:
                            old_key_path = old_path.get("key_path")
                            if old_key_path:
                                # 清理可能的m3u8访问计数器
                                pattern = f"m3u8_access_count_v2:*{old_key_path}*"
                                old_keys = await redis_client.keys(pattern)
                                if old_keys:
                                    await redis_client.delete(*old_keys)
                                    logger.info(f"清理旧路径 {old_key_path} 的 {len(old_keys)} 个访问计数器")
                    
                    existing_data["paths"] = existing_paths
                    existing_data["key_path"] = key_path
                    logger.info(f"为CIDR模式 {normalized_pattern} 添加新路径: {key_path}, 总路径数: {len(existing_paths)}")
                else:
                    # 路径已存在，更新时间戳
                    for p in existing_paths:
                        if p.get("key_path") == key_path:
                            p["created_at"] = current_time
                            break
                    existing_data["paths"] = existing_paths
                    logger.info(f"更新CIDR模式 {normalized_pattern} 现有路径时间戳: {key_path}")
                
                whitelist_data = existing_data
                merged_count = 1
                new_count = 0
            except json.JSONDecodeError:
                pass
        
        # UID级别UA+IP对管理：追踪所有UA+IP组合
        uid_pairs_key = f"uid_ua_ip_pairs:{uid}"
        ua_ip_pair_id = f"{normalized_pattern}:{ua_hash}"
        
        # 获取当前UID的所有UA+IP对
        uid_pairs_data_str = await redis_client.get(uid_pairs_key)
        uid_pairs = []
        removed_pairs = []
        
        if uid_pairs_data_str:
            try:
                uid_pairs = json.loads(uid_pairs_data_str)
            except json.JSONDecodeError:
                uid_pairs = []
        
        # 检查当前UA+IP对是否已存在
        existing_pair = None
        for pair in uid_pairs:
            if pair.get("pair_id") == ua_ip_pair_id:
                existing_pair = pair
                break
        
        if existing_pair:
            # 更新现有对的时间戳
            existing_pair["last_updated"] = current_time
        else:
            # 添加新的UA+IP对
            new_pair = {
                "pair_id": ua_ip_pair_id,
                "ip_pattern": normalized_pattern,
                "ua_hash": ua_hash,
                "created_at": current_time,
                "last_updated": current_time
            }
            uid_pairs.append(new_pair)
            
            # 如果超过最大数量，移除最旧的（FIFO）
            if len(uid_pairs) > config.MAX_UA_IP_PAIRS_PER_UID:
                uid_pairs.sort(key=lambda x: x.get("created_at", 0))
                removed_pairs = uid_pairs[:-config.MAX_UA_IP_PAIRS_PER_UID]
                uid_pairs = uid_pairs[-config.MAX_UA_IP_PAIRS_PER_UID:]
                
                # 清理被移除的UA+IP对的Redis键
                for old_pair in removed_pairs:
                    old_pair_id = old_pair.get("pair_id", "")
                    if old_pair_id and ":" in old_pair_id:
                        try:
                            old_ip_pattern, old_ua_hash = old_pair_id.rsplit(":", 1)
                            old_redis_key = f"ip_cidr_access:{old_ip_pattern.replace('/', '_')}:{old_ua_hash}"
                            await redis_client.delete(old_redis_key)
                            logger.info(f"清理旧UA+IP对: uid={uid}, pair_id={old_pair_id}")
                        except ValueError as e:
                            logger.error(f"清理旧UA+IP对失败，pair_id格式无效: {old_pair_id}, error={str(e)}")
        
        # 存储更新的UID级别UA+IP对列表
        await redis_client.set(uid_pairs_key, json.dumps(uid_pairs), ex=config.IP_ACCESS_TTL)
        
        # 存储更新的IP+UA数据
        await redis_client.set(redis_key, json.dumps(whitelist_data), ex=config.IP_ACCESS_TTL)
        
        # 生成CIDR示例用于调试
        cidr_examples = CIDRMatcher.expand_cidr_examples(normalized_pattern, 3)
        
        logger.info(f"存储IP模式成功: patterns=[{normalized_pattern}], ua_hash={ua_hash}, TTL={config.IP_ACCESS_TTL}s")
        logger.info(f"UID UA+IP对管理: uid={uid}, total_pairs={len(uid_pairs)}, removed_pairs={len(removed_pairs)}")
        
        return {
            "success": True,
            "message": "CIDR whitelist added/updated successfully",
            "key_path": key_path,
            "ip_pattern": normalized_pattern,
            "cidr_examples": cidr_examples,
            "ua_hash": ua_hash,
            "ttl": config.IP_ACCESS_TTL,
            "patterns_merged": merged_count,
            "patterns_new": new_count,
            "multi_path_info": {
                "max_paths_per_cidr": config.MAX_PATHS_PER_CIDR,
                "current_path": key_path,
                "path_replacement_policy": "FIFO (oldest paths are removed when limit exceeded)"
            },
            "uid_ua_ip_pairs_info": {
                "max_pairs_per_uid": config.MAX_UA_IP_PAIRS_PER_UID,
                "current_pairs_count": len(uid_pairs),
                "pairs_removed": len(removed_pairs),
                "pair_replacement_policy": "FIFO (oldest UA+IP pairs are removed when limit exceeded)"
            }
        }
        
    except Exception as e:
        logger.error(f"add_ip_whitelist error: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to add IP to whitelist: {str(e)}"
        }


async def add_static_file_whitelist(
    uid: str,
    target_client_ip: str,
    user_agent: str
) -> Dict[str, Any]:
    """
    添加UA+IP到静态文件白名单（独立存储，无需路径）
    
    Args:
        uid: 用户ID
        target_client_ip: 目标客户端IP
        user_agent: User-Agent
    
    Returns:
        Result dictionary with success/error information
    """
    redis_client = redis_service.get_client()
    
    try:
        # 标准化IP地址（自动转换为/24子网）
        if CIDRMatcher.is_valid_ip(target_client_ip) or CIDRMatcher.is_cidr_notation(target_client_ip):
            normalized_pattern = CIDRMatcher.normalize_cidr(target_client_ip)
            logger.info(f"静态文件白名单 - 已标准化IP模式: {target_client_ip} -> {normalized_pattern}")
        else:
            return {
                "success": False,
                "error": f"Invalid IP address or CIDR: {target_client_ip}"
            }
        
        ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        current_time = int(time.time())
        
        # 使用独立的Redis键格式存储静态文件白名单
        redis_key = f"static_file_access:{normalized_pattern.replace('/', '_')}:{ua_hash}"
        
        # 构建数据结构
        whitelist_data = {
            "uid": uid,
            "ip_patterns": [normalized_pattern],
            "user_agent": user_agent,
            "created_at": current_time,
            "access_type": "static_files_only"
        }
        
        # UID级别UA+IP对管理：追踪所有UA+IP组合
        uid_pairs_key = f"uid_static_ua_ip_pairs:{uid}"
        ua_ip_pair_id = f"{normalized_pattern}:{ua_hash}"
        
        # 获取当前UID的所有UA+IP对
        uid_pairs_data_str = await redis_client.get(uid_pairs_key)
        uid_pairs = []
        removed_pairs = []
        
        if uid_pairs_data_str:
            try:
                uid_pairs = json.loads(uid_pairs_data_str)
            except json.JSONDecodeError:
                uid_pairs = []
        
        # 检查当前UA+IP对是否已存在
        existing_pair = None
        for pair in uid_pairs:
            if pair.get("pair_id") == ua_ip_pair_id:
                existing_pair = pair
                break
        
        if existing_pair:
            # 更新现有对的时间戳
            existing_pair["last_updated"] = current_time
        else:
            # 添加新的UA+IP对
            new_pair = {
                "pair_id": ua_ip_pair_id,
                "ip_pattern": normalized_pattern,
                "ua_hash": ua_hash,
                "created_at": current_time,
                "last_updated": current_time
            }
            uid_pairs.append(new_pair)
            
            # 如果超过最大数量，移除最旧的（FIFO）
            if len(uid_pairs) > config.MAX_UA_IP_PAIRS_PER_UID:
                uid_pairs.sort(key=lambda x: x.get("created_at", 0))
                removed_pairs = uid_pairs[:-config.MAX_UA_IP_PAIRS_PER_UID]
                uid_pairs = uid_pairs[-config.MAX_UA_IP_PAIRS_PER_UID:]
                
                # 清理被移除的UA+IP对的Redis键
                for old_pair in removed_pairs:
                    old_pair_id = old_pair.get("pair_id", "")
                    if old_pair_id and ":" in old_pair_id:
                        try:
                            old_ip_pattern, old_ua_hash = old_pair_id.rsplit(":", 1)
                            old_redis_key = f"static_file_access:{old_ip_pattern.replace('/', '_')}:{old_ua_hash}"
                            await redis_client.delete(old_redis_key)
                            logger.info(f"清理旧静态文件UA+IP对: uid={uid}, pair_id={old_pair_id}")
                        except ValueError as e:
                            logger.error(f"清理旧静态文件UA+IP对失败，pair_id格式无效: {old_pair_id}, error={str(e)}")
        
        # 存储更新的UID级别UA+IP对列表
        await redis_client.set(uid_pairs_key, json.dumps(uid_pairs), ex=config.IP_ACCESS_TTL)
        
        # 存储静态文件白名单数据
        await redis_client.set(redis_key, json.dumps(whitelist_data), ex=config.IP_ACCESS_TTL)
        
        # 生成CIDR示例用于调试
        cidr_examples = CIDRMatcher.expand_cidr_examples(normalized_pattern, 3)
        
        logger.info(f"存储静态文件白名单成功: patterns=[{normalized_pattern}], ua_hash={ua_hash}, TTL={config.IP_ACCESS_TTL}s")
        logger.info(f"UID 静态文件UA+IP对管理: uid={uid}, total_pairs={len(uid_pairs)}, removed_pairs={len(removed_pairs)}")
        
        return {
            "success": True,
            "message": "Static file whitelist added/updated successfully",
            "ip_pattern": normalized_pattern,
            "cidr_examples": cidr_examples,
            "ua_hash": ua_hash,
            "ttl": config.IP_ACCESS_TTL,
            "uid_static_ua_ip_pairs_info": {
                "max_pairs_per_uid": config.MAX_UA_IP_PAIRS_PER_UID,
                "current_pairs_count": len(uid_pairs),
                "pairs_removed": len(removed_pairs),
                "pair_replacement_policy": "FIFO (oldest UA+IP pairs are removed when limit exceeded)"
            }
        }
        
    except Exception as e:
        logger.error(f"add_static_file_whitelist error: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to add static file whitelist: {str(e)}"
        }


async def check_static_file_access(client_ip: str, user_agent: str) -> Tuple[bool, Optional[str]]:
    """
    检查IP+UA是否有权访问静态文件（独立白名单）
    
    Args:
        client_ip: 客户端IP
        user_agent: User-Agent
    
    Returns:
        (is_allowed, uid)
    """
    redis_client = redis_service.get_client()
    try:
        ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        
        # 查找所有匹配的静态文件访问键
        pattern = f"static_file_access:*:{ua_hash}"
        static_keys = await redis_client.keys(pattern)
        
        for static_key in static_keys:
            static_data = await redis_client.get(static_key)
            if static_data:
                try:
                    data = json.loads(static_data)
                    ip_patterns = data.get("ip_patterns", [])
                    
                    # 使用CIDR匹配检查IP
                    is_match, matched_pattern = CIDRMatcher.match_ip_against_patterns(client_ip, ip_patterns)
                    if is_match:
                        uid = data.get("uid")
                        logger.info(f"✅ 静态文件白名单验证成功: IP={client_ip} 匹配模式={matched_pattern}, uid={uid}")
                        return True, uid
                except json.JSONDecodeError:
                    continue
        
        logger.debug(f"静态文件白名单未找到匹配: IP={client_ip}, UA hash={ua_hash}")
        return False, None
        
    except Exception as e:
        logger.error(f"检查静态文件访问失败: IP={client_ip}, error={str(e)}")
        return False, None
