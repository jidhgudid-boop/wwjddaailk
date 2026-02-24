"""
监控路由
Health check, stats, and monitoring endpoints
"""
import os
import time
import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, FileResponse

from models.config import config
from services.redis_service import redis_service
from services.access_log_service import (
    get_denied_access_logs,
    get_recent_access_logs,
    get_access_logs_summary
)
from services.token_replay_service import (
    get_replay_logs,
    get_replay_logs_summary
)
from services.key_protect_service import (
    get_key_access_logs,
    get_key_access_summary,
    get_m3u8_cache_stats
)

# 导入性能优化器状态
try:
    from performance_optimizer import UVLOOP_AVAILABLE
except ImportError:
    UVLOOP_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局流量收集器（将在应用启动时设置）
traffic_collector = None

# 全局流式代理服务（将在应用启动时设置）
stream_proxy_service = None


def set_traffic_collector(collector):
    """设置全局流量收集器实例"""
    global traffic_collector
    traffic_collector = collector


def set_stream_proxy_service(service):
    """设置全局流式代理服务实例"""
    global stream_proxy_service
    stream_proxy_service = service


@router.get("/health")
async def health_check():
    """健康检查端点"""
    try:
        # 测试 Redis 连接
        redis_client = redis_service.get_client()
        start_time = time.time()
        await redis_client.ping()
        redis_latency = (time.time() - start_time) * 1000
        
        # 检查流量收集器状态
        traffic_status = "disabled"
        if config.TRAFFIC_COLLECTOR_ENABLED:
            if traffic_collector:
                traffic_status = "running" if traffic_collector._running else "stopped"
            else:
                traffic_status = "not_initialized"
        
        return {
            "status": "healthy",
            "timestamp": int(time.time()),
            "redis": {
                "status": "connected",
                "latency_ms": round(redis_latency, 2)
            },
            "http_client": {
                "status": "active"
            },
            "traffic_collector": {
                "enabled": config.TRAFFIC_COLLECTOR_ENABLED,
                "status": traffic_status
            },
            "worker_pid": os.getpid(),
            "config": {
                "http2_enabled": True,
                "streaming_enabled": config.ENABLE_RESPONSE_STREAMING,
                "parallel_validation": config.ENABLE_PARALLEL_VALIDATION,
                "redis_pipeline": config.ENABLE_REDIS_PIPELINE,
                "request_deduplication": config.ENABLE_REQUEST_DEDUPLICATION,
                "chunk_size": config.STREAM_CHUNK_SIZE,
                "max_connections": config.HTTP_CONNECTOR_LIMIT
            },
            "performance_optimization": {
                "uvloop_enabled": UVLOOP_AVAILABLE,
                "optimizer_enabled": True,
                "optimization_level": "high" if UVLOOP_AVAILABLE else "medium"
            }
        }
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        return JSONResponse(
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": int(time.time())
            },
            status_code=503
        )


@router.get("/stats")
async def performance_stats():
    """性能统计端点"""
    try:
        redis_client = redis_service.get_client()
        
        # 获取活跃session数量
        try:
            session_keys = await redis_client.keys("session:*")
            active_sessions = len(session_keys)
        except:
            active_sessions = "N/A"
        
        # 获取活跃用户数量
        try:
            user_keys = await redis_client.keys("user_active_session:*")
            active_users = len(user_keys)
        except:
            active_users = "N/A"
        
        # 获取m3u8使用记录数量
        try:
            m3u8_keys = await redis_client.keys("m3u8_*:*")
            m3u8_uses = len(m3u8_keys)
        except:
            m3u8_uses = "N/A"
        
        # 获取IP访问记录数量
        try:
            ip_keys = await redis_client.keys("ip_*:*")
            ip_accesses = len(ip_keys)
        except:
            ip_accesses = "N/A"
        
        return {
            "timestamp": int(time.time()),
            "worker_pid": os.getpid(),
            "redis_stats": {
                "active_sessions": active_sessions,
                "active_users": active_users,
                "m3u8_single_uses": m3u8_uses,
                "ip_accesses": ip_accesses
            },
            "system_info": {
                "python_version": f"Python {'.'.join(map(str, os.sys.version_info[:3]))}",
                "process_id": os.getpid()
            }
        }
    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}")
        return JSONResponse(
            content={
                "error": str(e),
                "timestamp": int(time.time())
            },
            status_code=500
        )


@router.get("/monitor")
async def monitor_dashboard():
    """监控面板"""
    monitor_file = os.path.join(os.path.dirname(__file__), "..", "static", "monitor.html")
    if os.path.exists(monitor_file):
        return FileResponse(monitor_file, media_type="text/html")
    return JSONResponse(
        content={"error": "Monitor dashboard not found"},
        status_code=404
    )


@router.get("/traffic")
async def traffic_stats():
    """流量收集器统计接口"""
    try:
        if not config.TRAFFIC_COLLECTOR_ENABLED:
            return {
                "status": "disabled",
                "message": "流量收集器未启用"
            }
        
        if not traffic_collector:
            return {
                "status": "not_initialized",
                "message": "流量收集器未初始化"
            }
        
        status = traffic_collector.get_current_status()
        status["timestamp"] = int(time.time())
        
        return status
        
    except Exception as e:
        return JSONResponse(
            content={
                "error": f"获取流量统计失败: {str(e)}",
                "timestamp": int(time.time()),
                "worker_pid": os.getpid()
            },
            status_code=500
        )


@router.get("/active-transfers")
async def active_transfers():
    """实时传输监控接口"""
    try:
        if not stream_proxy_service:
            return {
                "status": "not_initialized",
                "message": "流式代理服务未初始化",
                "active_transfers": 0,
                "transfers": []
            }
        
        transfers_info = stream_proxy_service.get_active_transfers()
        transfers_info["worker_pid"] = os.getpid()
        
        return transfers_info
        
    except Exception as e:
        return JSONResponse(
            content={
                "error": f"获取活动传输失败: {str(e)}",
                "timestamp": int(time.time()),
                "worker_pid": os.getpid()
            },
            status_code=500
        )


@router.get("/whitelist-info")
async def whitelist_info():
    """获取白名单信息"""
    try:
        import json
        import hashlib
        redis_client = redis_service.get_client()
        
        # 获取所有CIDR白名单键
        all_keys = await redis_client.keys("ip_cidr_access:*")
        
        whitelist_entries = []
        current_time = int(time.time())
        
        for key in all_keys[:50]:  # 限制返回数量
            try:
                data_str = await redis_client.get(key)
                if data_str:
                    data = json.loads(data_str)
                    ttl = await redis_client.ttl(key)
                    
                    # 提取信息
                    entry = {
                        "uid": data.get("uid", "unknown"),
                        "ip_patterns": data.get("ip_patterns", []),
                        "ua_hash": key.decode().split(":")[-1] if isinstance(key, bytes) else key.split(":")[-1],
                        "paths": data.get("paths", []),
                        "created_at": data.get("created_at", 0),
                        "ttl_seconds": ttl if ttl > 0 else 0,
                        "expires_at": current_time + ttl if ttl > 0 else None
                    }
                    whitelist_entries.append(entry)
            except Exception as e:
                logger.error(f"解析白名单条目失败: {key}, error={str(e)}")
                continue
        
        # 按创建时间排序
        whitelist_entries.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        
        return {
            "total_entries": len(whitelist_entries),
            "entries": whitelist_entries,
            "timestamp": current_time
        }
        
    except Exception as e:
        return JSONResponse(
            content={
                "error": f"获取白名单信息失败: {str(e)}",
                "timestamp": int(time.time())
            },
            status_code=500
        )


@router.get("/probe/backend")
async def probe_backend_file(
    path: str = Query(..., description="Path to probe on backend server")
):
    """后端文件探测接口"""
    from services.http_client import http_client_service
    from utils.helpers import get_client_ip
    from fastapi import Request
    
    try:
        if not path or ".." in path:
            return JSONResponse(
                content={"status": "error", "reason": "invalid_path"},
                status_code=400
            )
        
        # 路径拼接
        backend_scheme = "https" if config.BACKEND_USE_HTTPS else "http"
        backend_url = f"{backend_scheme}://{config.BACKEND_HOST}:{config.BACKEND_PORT}"
        backend_url += path if path.startswith('/') else '/' + path
        
        # 设置请求头
        headers = {
            "User-Agent": "ProbeAgent/1.0",
            "Host": config.PROXY_HOST_HEADER
        }
        
        logger.info(f"[probe_backend_file] backend_url={backend_url}")
        
        # 发起探测请求
        http_client = await http_client_service.get_client()
        try:
            response = await http_client.get(
                backend_url,
                headers=headers,
                timeout=10.0
            )
            
            result = {
                "status": "ok" if response.status_code == 200 else "fail",
                "backend_status": response.status_code,
                "reason": response.reason_phrase,
                "content_type": response.headers.get("Content-Type", ""),
                "backend_url": backend_url,
                "headers": dict(response.headers)
            }
            return result
            
        except Exception as e:
            return JSONResponse(
                content={
                    "status": "error",
                    "reason": f"backend_unreachable: {str(e)}",
                    "backend_url": backend_url
                },
                status_code=502
            )
            
    except Exception as e:
        return JSONResponse(
            content={
                "status": "error",
                "reason": f"internal_error: {str(e)}"
            },
            status_code=500
        )


@router.get("/api/access-logs/denied")
async def get_denied_logs(limit: int = Query(100, ge=1, le=100)):
    """
    获取被拒绝的访问日志
    
    Args:
        limit: 返回的最大记录数 (1-100)
    """
    try:
        logs = await get_denied_access_logs(limit)
        summary = await get_access_logs_summary()
        
        return {
            "status": "ok",
            "total": summary.get("denied_count", 0),
            "limit": limit,
            "records": logs,
            "timestamp": int(time.time())
        }
    except Exception as e:
        logger.error(f"获取拒绝访问日志失败: {str(e)}")
        return JSONResponse(
            content={
                "status": "error",
                "error": str(e),
                "timestamp": int(time.time())
            },
            status_code=500
        )


@router.get("/api/access-logs/recent")
async def get_recent_logs(limit: int = Query(100, ge=1, le=100)):
    """
    获取最近成功的访问日志
    
    Args:
        limit: 返回的最大记录数 (1-100)
    """
    try:
        logs = await get_recent_access_logs(limit)
        summary = await get_access_logs_summary()
        
        return {
            "status": "ok",
            "total": summary.get("recent_count", 0),
            "limit": limit,
            "records": logs,
            "timestamp": int(time.time())
        }
    except Exception as e:
        logger.error(f"获取最近访问日志失败: {str(e)}")
        return JSONResponse(
            content={
                "status": "error",
                "error": str(e),
                "timestamp": int(time.time())
            },
            status_code=500
        )


@router.get("/api/access-logs/summary")
async def get_logs_summary():
    """
    获取访问日志摘要统计
    """
    try:
        summary = await get_access_logs_summary()
        summary["timestamp"] = int(time.time())
        return summary
    except Exception as e:
        logger.error(f"获取访问日志摘要失败: {str(e)}")
        return JSONResponse(
            content={
                "status": "error",
                "error": str(e),
                "timestamp": int(time.time())
            },
            status_code=500
        )


@router.get("/api/replay-logs")
async def get_token_replay_logs(limit: int = Query(300, ge=1, le=300)):
    """
    获取 Token 重放日志
    
    Args:
        limit: 返回的最大记录数 (1-300)
    """
    try:
        logs = await get_replay_logs(limit)
        summary = await get_replay_logs_summary()
        
        return {
            "status": "ok",
            "total": summary.get("total_count", 0),
            "recent_blocked": summary.get("recent_blocked_count", 0),
            "limit": limit,
            "records": logs,
            "timestamp": int(time.time())
        }
    except Exception as e:
        logger.error(f"获取重放日志失败: {str(e)}")
        return JSONResponse(
            content={
                "status": "error",
                "error": str(e),
                "timestamp": int(time.time())
            },
            status_code=500
        )


@router.get("/api/replay-logs/summary")
async def get_token_replay_logs_summary():
    """
    获取重放日志摘要统计
    """
    try:
        summary = await get_replay_logs_summary()
        summary["timestamp"] = int(time.time())
        return summary
    except Exception as e:
        logger.error(f"获取重放日志摘要失败: {str(e)}")
        return JSONResponse(
            content={
                "status": "error",
                "error": str(e),
                "timestamp": int(time.time())
            },
            status_code=500
        )


@router.get("/api/key-access-logs")
async def get_key_access_logs_api(limit: int = Query(300, ge=1, le=300)):
    """
    获取 Key 文件访问日志
    
    Args:
        limit: 返回的最大记录数 (1-300)
    """
    try:
        logs = await get_key_access_logs(limit)
        summary = await get_key_access_summary()
        
        return {
            "status": "ok",
            "total": summary.get("total_count", 0),
            "recent_blocked": summary.get("recent_blocked_count", 0),
            "recent_max_exceeded": summary.get("recent_max_exceeded_count", 0),
            "limit": limit,
            "records": logs,
            "timestamp": int(time.time())
        }
    except Exception as e:
        logger.error(f"获取 Key 访问日志失败: {str(e)}")
        return JSONResponse(
            content={
                "status": "error",
                "error": str(e),
                "total": 0,
                "recent_blocked": 0,
                "recent_max_exceeded": 0,
                "records": [],
                "timestamp": int(time.time())
            },
            status_code=500
        )


@router.get("/api/key-access-logs/summary")
async def get_key_access_logs_summary_api():
    """
    获取 Key 文件访问日志摘要统计
    """
    try:
        summary = await get_key_access_summary()
        summary["timestamp"] = int(time.time())
        summary["status"] = "ok"
        return summary
    except Exception as e:
        logger.error(f"获取 Key 访问日志摘要失败: {str(e)}")
        return JSONResponse(
            content={
                "status": "error",
                "error": str(e),
                "timestamp": int(time.time())
            },
            status_code=500
        )


@router.get("/api/m3u8-cache-stats")
async def get_m3u8_cache_stats_api():
    """
    获取 M3U8 缓存统计信息
    """
    try:
        stats = await get_m3u8_cache_stats()
        return stats
    except Exception as e:
        logger.error(f"获取 M3U8 缓存统计失败: {str(e)}")
        return JSONResponse(
            content={
                "status": "error",
                "error": str(e),
                "cache_count": 0,
                "timestamp": int(time.time())
            },
            status_code=500
        )
