"""
调试路由
Debug endpoints for browser detection, CIDR testing, etc.
"""
import os
import time
import logging
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

from models.config import config
from utils.browser_detector import BrowserDetector
from utils.cidr_matcher import CIDRMatcher

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/debug/browser")
async def browser_detection_debug(
    request: Request,
    ua: str = Query(None, description="User-Agent string to test")
):
    """浏览器检测调试接口"""
    try:
        user_agent = ua or request.headers.get("User-Agent", "")
        
        if not user_agent:
            return JSONResponse(
                content={
                    "error": "请提供 User-Agent (通过 ?ua= 参数或 User-Agent 头)",
                    "example": "/debug/browser?ua=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                status_code=400
            )
        
        # 获取详细检测信息
        debug_info = BrowserDetector.debug_detection(user_agent)
        
        # 获取配置的访问限制
        browser_type, browser_name, suggested_max_count = BrowserDetector.detect_browser_type(user_agent)
        
        if config.ENABLE_BROWSER_ADAPTIVE_ACCESS:
            access_limits = config.M3U8_ACCESS_LIMITS.get(browser_type, {})
            final_max_count = access_limits.get(browser_name, access_limits.get('default', suggested_max_count))
            access_window_ttl = config.M3U8_ACCESS_WINDOW_TTL.get(browser_type, 60)
        else:
            final_max_count = config.M3U8_DEFAULT_MAX_ACCESS_COUNT
            access_window_ttl = getattr(config, 'M3U8_SINGLE_USE_TTL', 60)
        
        response_data = {
            "detection_result": {
                "browser_type": browser_type,
                "browser_name": browser_name,
                "suggested_max_count": suggested_max_count,
                "final_max_count": final_max_count,
                "access_window_ttl": access_window_ttl
            },
            "debug_details": debug_info,
            "config_info": {
                "browser_adaptive_access_enabled": config.ENABLE_BROWSER_ADAPTIVE_ACCESS,
                "detailed_logging_enabled": config.ENABLE_DETAILED_ACCESS_LOGGING,
                "access_limits": config.M3U8_ACCESS_LIMITS,
                "window_ttls": config.M3U8_ACCESS_WINDOW_TTL
            },
            "timestamp": int(time.time()),
            "worker_pid": os.getpid()
        }
        
        return response_data
        
    except Exception as e:
        return JSONResponse(
            content={
                "error": f"浏览器检测调试失败: {str(e)}",
                "timestamp": int(time.time()),
                "worker_pid": os.getpid()
            },
            status_code=500
        )


@router.get("/debug/cidr")
async def cidr_debug(
    ip: str = Query(..., description="IP address or CIDR to test"),
    test_ip: str = Query(None, description="IP address to test against CIDR")
):
    """CIDR 调试接口"""
    try:
        # 检查是否为有效IP或CIDR
        is_valid = CIDRMatcher.is_valid_ip(ip) or CIDRMatcher.is_cidr_notation(ip)
        
        if not is_valid:
            return JSONResponse(
                content={
                    "error": f"Invalid IP address or CIDR: {ip}",
                    "example": "/debug/cidr?ip=192.168.1.0/24&test_ip=192.168.1.100"
                },
                status_code=400
            )
        
        # 标准化CIDR
        normalized = CIDRMatcher.normalize_cidr(ip)
        
        # 生成示例
        examples = CIDRMatcher.expand_cidr_examples(normalized, 5)
        
        result = {
            "input": ip,
            "is_cidr": CIDRMatcher.is_cidr_notation(ip),
            "is_single_ip": CIDRMatcher.is_valid_ip(ip) and not CIDRMatcher.is_cidr_notation(ip),
            "normalized": normalized,
            "examples": examples,
            "timestamp": int(time.time())
        }
        
        # 如果提供了测试IP，检查是否匹配
        if test_ip:
            if CIDRMatcher.is_valid_ip(test_ip):
                matches = CIDRMatcher.ip_in_cidr(test_ip, normalized)
                result["test_result"] = {
                    "test_ip": test_ip,
                    "matches": matches
                }
            else:
                result["test_result"] = {
                    "test_ip": test_ip,
                    "error": "Invalid test IP address"
                }
        
        return result
        
    except Exception as e:
        return JSONResponse(
            content={
                "error": f"CIDR调试失败: {str(e)}",
                "timestamp": int(time.time())
            },
            status_code=500
        )


@router.get("/debug/ip-whitelist")
async def ip_whitelist_debug(request: Request):
    """IP白名单调试接口"""
    from services.redis_service import redis_service
    from utils.helpers import get_client_ip
    
    try:
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "unknown")
        
        redis_client = redis_service.get_client()
        
        # 查找所有白名单记录
        import hashlib
        ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        cidr_pattern = f"ip_cidr_access:*:{ua_hash}"
        cidr_keys = await redis_client.keys(cidr_pattern)
        
        whitelist_entries = []
        matching_entries = []
        
        for key in cidr_keys:
            data_str = await redis_client.get(key)
            if data_str:
                try:
                    import json
                    data = json.loads(data_str)
                    entry = {
                        "key": key,
                        "ip_patterns": data.get("ip_patterns", []),
                        "paths": data.get("paths", []),
                        "uid": data.get("uid"),
                        "created_at": data.get("created_at")
                    }
                    whitelist_entries.append(entry)
                    
                    # 检查是否匹配当前IP
                    ip_patterns = data.get("ip_patterns", [])
                    is_match, matched_pattern = CIDRMatcher.match_ip_against_patterns(client_ip, ip_patterns)
                    if is_match:
                        entry["matched_pattern"] = matched_pattern
                        matching_entries.append(entry)
                except:
                    pass
        
        return {
            "client_ip": client_ip,
            "user_agent": user_agent,
            "ua_hash": ua_hash,
            "total_whitelist_entries": len(whitelist_entries),
            "matching_entries_count": len(matching_entries),
            "all_entries": whitelist_entries,
            "matching_entries": matching_entries,
            "timestamp": int(time.time())
        }
        
    except Exception as e:
        return JSONResponse(
            content={
                "error": f"IP白名单调试失败: {str(e)}",
                "timestamp": int(time.time())
            },
            status_code=500
        )


@router.get("/debug/session")
async def session_debug(
    request: Request,
    uid: str = Query(None, description="User ID"),
    path: str = Query("", description="Path to check")
):
    """会话调试端点"""
    from services.redis_service import redis_service
    from services.session_service import validate_session_internal
    from utils.helpers import get_client_ip, extract_match_key
    import hashlib
    import json
    
    try:
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "unknown")
        session_id = request.cookies.get(config.SESSION_COOKIE_NAME) or request.headers.get("X-Session-ID")
        
        redis_client = redis_service.get_client()
        response_data = {
            "client_ip": client_ip,
            "user_agent": user_agent[:100] + "..." if len(user_agent) > 100 else user_agent,
            "session_id": session_id,
            "uid": uid,
            "path": path,
            "timestamp": int(time.time()),
            "worker_pid": os.getpid()
        }
        
        # Check session data
        if session_id:
            session_data = await validate_session_internal(redis_client, session_id, client_ip, user_agent)
            response_data["session_data"] = session_data
            response_data["session_valid"] = bool(session_data)
        
        # Check IP+UA session
        if uid and path:
            key_path = extract_match_key(path)
            ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
            session_key = f"ip_ua_session:{client_ip}:{ua_hash}:{uid}:{key_path}"
            ip_ua_session_id = await redis_client.get(session_key)
            response_data["ip_ua_session_key"] = session_key
            response_data["ip_ua_session_id"] = ip_ua_session_id
            
            if ip_ua_session_id:
                ip_ua_session_data_str = await redis_client.get(f"session:{ip_ua_session_id}")
                response_data["ip_ua_session_data"] = json.loads(ip_ua_session_data_str) if ip_ua_session_data_str else None
        
        # Check whitelist
        ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        redis_key = f"ip_ua_access:{client_ip}:{ua_hash}"
        whitelist_key_path = await redis_client.get(redis_key)
        response_data["whitelist"] = {
            "ip_ua_key": redis_key,
            "key_path": whitelist_key_path
        }
        
        return response_data
        
    except Exception as e:
        return JSONResponse(
            content={
                "error": f"Session debug failed: {str(e)}",
                "timestamp": int(time.time()),
                "worker_pid": os.getpid()
            },
            status_code=500
        )
