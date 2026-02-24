"""
验证服务 - 提供并行验证和请求去重功能
Validation service with parallel validation and request deduplication support
"""
import asyncio
import hashlib
import time
import logging
from typing import Optional, Tuple, Dict, Any

from services.redis_service import redis_service
from services.auth_service import check_ip_key_path, is_ip_in_fixed_whitelist
from services.session_service import get_or_validate_session_by_ip_ua, validate_session
from models.config import config

logger = logging.getLogger(__name__)


class RequestDeduplicator:
    """请求去重器 - 防止相同请求的重复处理"""
    
    def __init__(self):
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
    
    def _generate_request_key(self, client_ip: str, path: str, user_agent: str, uid: Optional[str] = None) -> str:
        """生成请求的唯一标识"""
        key_parts = [client_ip, path, user_agent]
        if uid:
            key_parts.append(uid)
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    async def deduplicate(self, client_ip: str, path: str, user_agent: str, uid: Optional[str], 
                         validation_func):
        """
        对请求进行去重处理
        如果相同的请求正在处理中，等待第一个请求完成并返回其结果
        
        Args:
            client_ip: 客户端IP
            path: 请求路径
            user_agent: User-Agent
            uid: 用户ID
            validation_func: 验证函数（async callable）
            
        Returns:
            验证结果
        """
        request_key = self._generate_request_key(client_ip, path, user_agent, uid)
        
        # 检查是否有相同的请求正在处理
        async with self._lock:
            if request_key in self._pending_requests:
                logger.debug(f"请求去重：等待已有请求完成 key={request_key[:8]}")
                future = self._pending_requests[request_key]
                created_future = False
            else:
                # 创建新的Future来跟踪这个请求
                future = asyncio.Future()
                self._pending_requests[request_key] = future
                created_future = True
        
        # 如果我们创建了这个future，执行验证
        if created_future:
            try:
                result = await validation_func()
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
                raise
            finally:
                # 清理pending requests
                async with self._lock:
                    self._pending_requests.pop(request_key, None)
        
        # 等待并返回结果（无论是我们创建的还是其他请求创建的）
        return await future


# 全局请求去重器实例
_request_deduplicator = RequestDeduplicator()


async def parallel_validate(
    client_ip: str,
    path: str,
    user_agent: str,
    uid: Optional[str],
    skip_ip_check: bool = False,
    skip_session_check: bool = False
) -> Tuple[bool, Optional[str], Optional[str], Optional[str], bool, Optional[dict]]:
    """
    并行执行验证检查，提高验证性能
    
    Args:
        client_ip: 客户端IP
        path: 请求路径
        user_agent: User-Agent
        uid: 用户ID（可选）
        skip_ip_check: 是否跳过IP白名单检查
        skip_session_check: 是否跳过会话检查
    
    Returns:
        (is_allowed, whitelist_uid, effective_session_id, session_uid, new_session_created, validated_session_data)
    """
    # 首先检查固定白名单 - 如果在固定白名单中，直接放行，跳过所有验证
    if is_ip_in_fixed_whitelist(client_ip):
        logger.info(f"🔓 固定白名单放行（并行验证）: IP={client_ip}, path={path}")
        return True, "fixed_whitelist", None, "fixed_whitelist", False, None
    
    tasks = []
    
    # 任务1：IP白名单检查
    if not skip_ip_check:
        tasks.append(check_ip_key_path(client_ip, path, user_agent))
    else:
        # 创建一个返回测试值的协程
        async def skip_ip():
            return True, "test_user"
        tasks.append(skip_ip())
    
    # 任务2：会话验证
    if not skip_session_check:
        tasks.append(get_or_validate_session_by_ip_ua(uid, client_ip, user_agent, path))
    else:
        # 创建一个返回测试值的协程
        async def skip_session():
            return None, False, uid or "test_user"
        tasks.append(skip_session())
    
    # 并行执行所有验证任务
    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = (time.time() - start_time) * 1000
    
    logger.debug(f"并行验证完成: 耗时 {elapsed:.2f}ms")
    
    # 处理IP白名单检查结果
    ip_result = results[0]
    if isinstance(ip_result, Exception):
        logger.error(f"IP白名单检查失败: {str(ip_result)}")
        is_allowed, whitelist_uid = False, None
    else:
        is_allowed, whitelist_uid = ip_result
    
    # 处理会话验证结果
    session_result = results[1]
    if isinstance(session_result, Exception):
        logger.error(f"会话验证失败: {str(session_result)}")
        effective_session_id, new_session_created, session_uid = None, False, None
    else:
        effective_session_id, new_session_created, session_uid = session_result
    
    # 如果有会话ID，验证会话数据
    validated_session_data = None
    if effective_session_id:
        validated_session_data = await validate_session(effective_session_id, client_ip, user_agent)
    
    return is_allowed, whitelist_uid, effective_session_id, session_uid, new_session_created, validated_session_data


async def validate_with_deduplication(
    client_ip: str,
    path: str,
    user_agent: str,
    uid: Optional[str],
    skip_ip_check: bool = False,
    skip_session_check: bool = False
) -> Tuple[bool, Optional[str], Optional[str], Optional[str], bool, Optional[dict]]:
    """
    带请求去重的验证
    
    Returns:
        (is_allowed, whitelist_uid, effective_session_id, session_uid, new_session_created, validated_session_data)
    """
    async def do_validation():
        # 首先检查固定白名单 - 如果在固定白名单中，直接放行，跳过所有验证
        if is_ip_in_fixed_whitelist(client_ip):
            logger.info(f"🔓 固定白名单放行（顺序验证）: IP={client_ip}, path={path}")
            return True, "fixed_whitelist", None, "fixed_whitelist", False, None
        
        if config.ENABLE_PARALLEL_VALIDATION:
            return await parallel_validate(
                client_ip, path, user_agent, uid, skip_ip_check, skip_session_check
            )
        else:
            # 顺序验证（原始逻辑）
            if not skip_ip_check:
                is_allowed, whitelist_uid = await check_ip_key_path(client_ip, path, user_agent)
            else:
                is_allowed, whitelist_uid = True, "test_user"
            
            if not skip_session_check:
                effective_session_id, new_session_created, session_uid = await get_or_validate_session_by_ip_ua(
                    uid, client_ip, user_agent, path
                )
            else:
                effective_session_id, new_session_created, session_uid = None, False, uid or "test_user"
            
            validated_session_data = None
            if effective_session_id:
                validated_session_data = await validate_session(effective_session_id, client_ip, user_agent)
            
            return is_allowed, whitelist_uid, effective_session_id, session_uid, new_session_created, validated_session_data
    
    if config.ENABLE_REQUEST_DEDUPLICATION:
        return await _request_deduplicator.deduplicate(
            client_ip, path, user_agent, uid, do_validation
        )
    else:
        return await do_validation()
