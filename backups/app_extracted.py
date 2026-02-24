import hmac
import hashlib
import base64
import time
import traceback
import os
import re
import logging
import uuid
import json
import asyncio
import socket
import ipaddress
import ssl
from typing import Optional, Dict, Tuple, List, Any
import redis.asyncio as redis_async
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
import weakref
import sys
from traffic_collector import TrafficCollector, init_traffic_collector

# FastAPI 特定导入
from fastapi import FastAPI, Request, Response, HTTPException, Header, Cookie, Query, Depends, status, Body
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import httpx

# 导入性能优化器
try:
    from performance_optimizer import (
        PerformanceOptimizer,
        performance_metrics,
        adaptive_rate_limiter,
        get_performance_status,
        UVLOOP_AVAILABLE
    )
    PERFORMANCE_OPTIMIZER_ENABLED = True
except ImportError:
    PERFORMANCE_OPTIMIZER_ENABLED = False
    UVLOOP_AVAILABLE = False
    base_logger = logging.getLogger(__name__)
    base_logger.warning("性能优化器未加载 - 某些优化功能将不可用")


# === CIDR IP 匹配工具函数 ===
class CIDRMatcher:
    """CIDR IP匹配工具类，支持IPv4 CIDR表示法"""
    
    @staticmethod
    def is_cidr_notation(ip_or_cidr: str) -> bool:
        """检查字符串是否为CIDR表示法"""
        try:
            if '/' in ip_or_cidr:
                ipaddress.ip_network(ip_or_cidr, strict=False)
                return True
            return False
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
            return False
    
    @staticmethod
    def is_valid_ip(ip_str: str) -> bool:
        """检查字符串是否为有效IP地址"""
        try:
            ipaddress.ip_address(ip_str)
            return True
        except (ipaddress.AddressValueError, ValueError):
            return False
    
    @staticmethod
    def ip_in_cidr(ip_str: str, cidr_str: str) -> bool:
        """检查IP是否在CIDR范围内"""
        try:
            ip = ipaddress.ip_address(ip_str)
            network = ipaddress.ip_network(cidr_str, strict=False)
            return ip in network
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
            return False
    
    @staticmethod
    def normalize_cidr(ip_or_cidr: str) -> str:
        """标准化CIDR表示法，所有IP都转换为/24子网"""
        try:
            if '/' in ip_or_cidr:
                # 已经是CIDR格式
                ip_str, prefix = ip_or_cidr.split('/', 1)
                ip = ipaddress.ip_address(ip_str)
                if ip.version == 4:
                    # IPv4 - 强制转换为/24子网
                    network = ipaddress.ip_network(f"{ip}/24", strict=False)
                    return str(network)
                else:
                    # IPv6 保持原有前缀或使用/128
                    try:
                        network = ipaddress.ip_network(ip_or_cidr, strict=False)
                        return str(network)
                    except:
                        return f"{ip}/128"
            else:
                # 单个IP，转换为/24 CIDR子网
                ip = ipaddress.ip_address(ip_or_cidr)
                if ip.version == 4:
                    # 将IP转换为/24子网 (例如: 180.98.66.2 -> 180.98.66.0/24)
                    network = ipaddress.ip_network(f"{ip}/24", strict=False)
                    return str(network)
                else:
                    return f"{ip}/128"  # IPv6保持/128
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
            # 如果解析失败，返回原字符串
            return ip_or_cidr
    
    @staticmethod
    def match_ip_against_patterns(client_ip: str, stored_patterns: List[str]) -> Tuple[bool, str]:
        """
        检查客户端IP是否匹配存储的模式列表（支持CIDR和精确匹配）
        返回: (是否匹配, 匹配的模式)
        """
        if not CIDRMatcher.is_valid_ip(client_ip):
            return False, ""
        
        for pattern in stored_patterns:
            if not pattern:
                continue
                
            # 尝试CIDR匹配
            if CIDRMatcher.is_cidr_notation(pattern):
                if CIDRMatcher.ip_in_cidr(client_ip, pattern):
                    return True, pattern
            else:
                # 精确匹配（向后兼容）
                if client_ip == pattern:
                    return True, pattern
        
        return False, ""
    
    @staticmethod
    def expand_cidr_examples(cidr_str: str, max_examples: int = 5) -> List[str]:
        """为调试目的，展示CIDR包含的示例IP地址"""
        try:
            network = ipaddress.ip_network(cidr_str, strict=False)
            examples = []
            count = 0
            for ip in network.hosts():
                if count >= max_examples:
                    break
                examples.append(str(ip))
                count += 1
            # 如果是/32网络，直接返回该IP
            if network.prefixlen == 32:
                examples = [str(network.network_address)]
            return examples
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
            return []


# === 浏览器类型识别器 ===
# === 修复的浏览器类型识别器 ===
class BrowserDetector:
    """浏览器类型检测器，用于识别不同浏览器的访问模式"""
    
    # 移动浏览器 User-Agent 关键词 - 修复版
    MOBILE_BROWSERS = {
        'qq': (['QQBrowser', 'MQQBrowser'], ['Mobile', 'Android', 'iPhone']),
        'uc': (['UCBrowser', 'UCWEB'], ['Mobile', 'Android', 'iPhone']),
        'baidu': (['baiduboxapp', 'BaiduHD'], ['Mobile', 'Android', 'iPhone']),
        'sogou': (['SogouMobileBrowser', 'SogouSearch'], ['Mobile', 'Android', 'iPhone']),
        'chrome_mobile': (['Chrome/'], ['Mobile', 'Android', 'iPhone']),
        'safari_mobile': (['Safari/'], ['Mobile', 'iPhone', 'iPad']),
        'edge_mobile': (['Edge/', 'EdgA/', 'EdgiOS/'], ['Mobile', 'Android', 'iPhone']),
        'firefox_mobile': (['Firefox/', 'FxiOS/'], ['Mobile', 'Android', 'iPhone'])
    }
    
    # 桌面浏览器 User-Agent 关键词 - 修复版
    DESKTOP_BROWSERS = {
        'chrome': (['Chrome/'], ['Windows NT', 'Macintosh', 'X11; Linux']),
        'firefox': (['Firefox/'], ['Windows NT', 'Macintosh', 'X11; Linux']),
        'edge': (['Edge/', 'Edg/'], ['Windows NT', 'Macintosh']),
        'safari': (['Safari/', 'Version/'], ['Macintosh']),
        'opera': (['Opera/', 'OPR/'], ['Windows NT', 'Macintosh', 'X11; Linux'])
    }
    
    # 下载工具 User-Agent 关键词
    DOWNLOAD_TOOLS = [
        'wget', 'curl', 'aria2', 'axel', 'youtube-dl', 'yt-dlp',
        'ffmpeg', 'vlc', 'mpv', 'IDM', 'Thunder', 'BitComet',
        'uTorrent', 'qBittorrent', 'Transmission', 'Deluge',
        'FlashGet', 'FreeDownloadManager', 'EagleGet',
        'python-requests', 'urllib', 'httplib', 'Go-http-client',
        'node-fetch', 'axios', 'okhttp'
    ]
    
    @classmethod
    def detect_browser_type(cls, user_agent: str) -> Tuple[str, str, int]:
        """
        检测浏览器类型并返回相应的访问限制
        
        返回: (browser_type, browser_name, max_access_count)
        """
        if not user_agent:
            return "unknown", "unknown", 1
        
        user_agent_lower = user_agent.lower()
        
        # 检查是否为下载工具
        for tool in cls.DOWNLOAD_TOOLS:
            if tool.lower() in user_agent_lower:
                return "download_tool", tool, 1
        
        # 优先检查移动浏览器
        for browser_name, (primary_keywords, platform_keywords) in cls.MOBILE_BROWSERS.items():
            # 检查主要关键词
            has_primary = any(keyword.lower() in user_agent_lower for keyword in primary_keywords)
            # 检查平台关键词
            has_platform = any(keyword.lower() in user_agent_lower for keyword in platform_keywords)
            
            if has_primary and has_platform:
                # QQ 和 UC 浏览器允许更多次访问
                if browser_name in ['qq', 'uc']:
                    return "mobile_browser", browser_name, 3
                else:
                    return "mobile_browser", browser_name, 2
        
        # 检查桌面浏览器
        for browser_name, (primary_keywords, platform_keywords) in cls.DESKTOP_BROWSERS.items():
            # 检查主要关键词
            has_primary = any(keyword.lower() in user_agent_lower for keyword in primary_keywords)
            # 检查平台关键词（桌面环境）
            has_platform = any(keyword.lower() in user_agent_lower for keyword in platform_keywords)
            
            if has_primary and has_platform:
                return "desktop_browser", browser_name, 2
        
        # 如果没有匹配到特定浏览器，但包含常见浏览器关键词，给予基本访问权限
        if any(keyword in user_agent_lower for keyword in ['mozilla', 'webkit', 'chrome', 'safari', 'firefox', 'edge']):
            if any(keyword in user_agent_lower for keyword in ['mobile', 'android', 'iphone', 'ipad']):
                return "mobile_browser", "generic_mobile", 2
            else:
                return "desktop_browser", "generic_desktop", 2
        
        # 默认情况
        return "unknown", "unknown", 1
    
    @classmethod
    def get_access_window_ttl(cls, browser_type: str) -> int:
        """根据浏览器类型返回访问窗口 TTL"""
        if browser_type == "mobile_browser":
            return 3 * 60  # 移动浏览器 3 分钟窗口
        elif browser_type == "desktop_browser":
            return 2 * 60  # 桌面浏览器 2 分钟窗口
        else:
            return 1 * 60  # 其他情况 1 分钟窗口
    
    @classmethod
    def debug_detection(cls, user_agent: str) -> dict:
        """调试用函数，返回详细的检测信息"""
        if not user_agent:
            return {"error": "Empty user agent"}
        
        user_agent_lower = user_agent.lower()
        debug_info = {
            "user_agent": user_agent,
            "user_agent_lower": user_agent_lower,
            "download_tools_found": [],
            "mobile_browser_matches": {},
            "desktop_browser_matches": {},
            "final_result": None
        }
        
        # 检查下载工具
        for tool in cls.DOWNLOAD_TOOLS:
            if tool.lower() in user_agent_lower:
                debug_info["download_tools_found"].append(tool)
        
        # 检查移动浏览器
        for browser_name, (primary_keywords, platform_keywords) in cls.MOBILE_BROWSERS.items():
            primary_matches = [kw for kw in primary_keywords if kw.lower() in user_agent_lower]
            platform_matches = [kw for kw in platform_keywords if kw.lower() in user_agent_lower]
            
            if primary_matches or platform_matches:
                debug_info["mobile_browser_matches"][browser_name] = {
                    "primary_keywords": primary_matches,
                    "platform_keywords": platform_matches,
                    "has_both": bool(primary_matches and platform_matches)
                }
        
        # 检查桌面浏览器
        for browser_name, (primary_keywords, platform_keywords) in cls.DESKTOP_BROWSERS.items():
            primary_matches = [kw for kw in primary_keywords if kw.lower() in user_agent_lower]
            platform_matches = [kw for kw in platform_keywords if kw.lower() in user_agent_lower]
            
            if primary_matches or platform_matches:
                debug_info["desktop_browser_matches"][browser_name] = {
                    "primary_keywords": primary_matches,
                    "platform_keywords": platform_matches,
                    "has_both": bool(primary_matches and platform_matches)
                }
        
        # 获取最终结果
        debug_info["final_result"] = cls.detect_browser_type(user_agent)
        
        return debug_info




# 确保日志目录存在
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)



# === 异常分类处理器 ===
class ErrorHandler:
    """错误处理器，用于分类和处理不同类型的异常"""
    
    @staticmethod
    def is_client_disconnect_error(exception):
        """判断是否为客户端断开连接错误"""
        error_types = (
            'ClientConnectionResetError',
            'ConnectionResetError', 
            'BrokenPipeError',
            'ClientOSError',
            'ClientConnectorError'
        )
        error_messages = (
            'Cannot write to closing transport',
            'Connection reset by peer',
            'Broken pipe',
            'Transport is closing',
            'Connection lost'
        )
        
        exception_name = type(exception).__name__
        exception_str = str(exception).lower()
        
        return (exception_name in error_types or 
                any(msg.lower() in exception_str for msg in error_messages))
    
    @staticmethod
    def should_suppress_logging(exception):
        """判断是否应该抑制日志记录"""
        return ErrorHandler.is_client_disconnect_error(exception)



# === Custom Logging Adapter ===
class ClientIPAdapter(logging.LoggerAdapter):
    def __init__(self, logger, client_ip):
        super().__init__(logger, {'client_ip': client_ip})
    
    def process(self, msg, kwargs):
        return '[IP:%s] %s' % (self.extra['client_ip'], msg), kwargs

# === 性能优化配置（修复版）===
class OptimizedConfig:
    # Redis 配置
    REDIS_HOST = "127.0.0.1"
    REDIS_PORT = 6379
    REDIS_DB = 6
    REDIS_PASSWORD = "redis_2xc67x"
    
    # 性能优化器配置（如果可用，使用优化器推荐的值）
    if PERFORMANCE_OPTIMIZER_ENABLED:
        optimizer = PerformanceOptimizer()
        opt_config = optimizer.get_optimized_config()
        REDIS_POOL_SIZE = opt_config['REDIS_POOL_SIZE']
        HTTP_CONNECTOR_LIMIT = opt_config['HTTP_CONNECTOR_LIMIT']
        HTTP_CONNECTOR_LIMIT_PER_HOST = opt_config['HTTP_CONNECTOR_LIMIT_PER_HOST']
        HTTP_KEEPALIVE_TIMEOUT = opt_config['HTTP_KEEPALIVE_TIMEOUT']
        HTTP_CONNECT_TIMEOUT = opt_config['HTTP_CONNECT_TIMEOUT']
        HTTP_TOTAL_TIMEOUT = opt_config['HTTP_TOTAL_TIMEOUT']
        HTTP_DNS_CACHE_TTL = opt_config['HTTP_DNS_CACHE_TTL']
        STREAM_CHUNK_SIZE = opt_config['STREAM_CHUNK_SIZE']
        BUFFER_SIZE = opt_config['BUFFER_SIZE']
        ENABLE_REQUEST_DEDUPLICATION = opt_config['ENABLE_REQUEST_DEDUPLICATION']
        ENABLE_PARALLEL_VALIDATION = opt_config['ENABLE_PARALLEL_VALIDATION']
        ENABLE_REDIS_PIPELINE = opt_config['ENABLE_REDIS_PIPELINE']
        ENABLE_RESPONSE_STREAMING = opt_config['ENABLE_RESPONSE_STREAMING']
    else:
        # 默认配置
        REDIS_POOL_SIZE = 100
        HTTP_CONNECTOR_LIMIT = 100
        HTTP_CONNECTOR_LIMIT_PER_HOST = 30
        HTTP_KEEPALIVE_TIMEOUT = 30
        HTTP_CONNECT_TIMEOUT = 8
        HTTP_TOTAL_TIMEOUT = 45
        HTTP_DNS_CACHE_TTL = 500
        STREAM_CHUNK_SIZE = 8192
        BUFFER_SIZE = 64 * 1024
        ENABLE_REQUEST_DEDUPLICATION = True
        ENABLE_PARALLEL_VALIDATION = True
        ENABLE_REDIS_PIPELINE = True
        ENABLE_RESPONSE_STREAMING = True
    
    REDIS_POOL_RETRY = 3
    REDIS_SOCKET_KEEPALIVE = True
    # 修复：使用正确的socket选项格式
    REDIS_SOCKET_KEEPALIVE_OPTIONS = {
        socket.TCP_KEEPIDLE: 1,
        socket.TCP_KEEPINTVL: 3,
        socket.TCP_KEEPCNT: 5,
    }

    # 错误处理配置 - 新增
    ENABLE_ERROR_RECOVERY = True
    LOG_CLIENT_DISCONNECTS = False  # 是否记录客户端断开日志
    SUPPRESS_TRANSPORT_ERRORS = True  # 是否抑制传输错误
    
    # 流式传输优化 - 已在上面根据性能优化器配置
    # STREAM_CHUNK_SIZE 和 BUFFER_SIZE 已经设置
    HTTP_DNS_CACHE_TTL = HTTP_DNS_CACHE_TTL if PERFORMANCE_OPTIMIZER_ENABLED else 500
    # TTL 配置（秒）
    SESSION_TTL = 2 * 60 * 60  # 2小时
    M3U8_SINGLE_USE_TTL = 5 * 60  # 5分钟
    USER_SESSION_TTL = 4 * 60 * 60  # 4小时
    IP_ACCESS_TTL = 1 * 60 * 60  # 1小时
    TOKEN_EXTEND_TTL = 75 * 60  # 75分钟活跃延期
    
    # CIDR IP 配置
    MAX_PATHS_PER_CIDR = 3  # CIDR模式下每个IP段允许的最大路径数
    
    # Safe Key Protect 配置
    SAFE_KEY_PROTECT_ENABLED = False  # 启用安全密钥保护重定向
    SAFE_KEY_PROTECT_REDIRECT_BASE_URL = "https://v.yuelk.com/pyvideo2/keyroute/"  # 重定向基础URL
    # m3u8访问配置
    M3U8_MAX_ACCESS_COUNT = 1  # 允许访问的最大次数
    M3U8_ACCESS_WINDOW_TTL = 1 * 60  # 1分钟访问窗口

    # === 增强的 M3U8 访问控制配置 ===
    # 默认访问次数限制（向后兼容）
    M3U8_DEFAULT_MAX_ACCESS_COUNT = 1
    
    # 不同浏览器类型的访问次数限制
    M3U8_ACCESS_LIMITS = {
        'mobile_browser': {
            'qq': 2,         # QQ 浏览器允许 2 次
            'uc': 1,         # UC 浏览器允许 2 次
            'baidu': 1,      # 百度浏览器允许 2 次
            'chrome_mobile': 1,
            'safari_mobile': 1,
            'default': 1     # 其他移动浏览器默认 2 次
        },
        'desktop_browser': {
            'chrome': 1,     # 桌面 Chrome 允许 2 次
            'firefox': 1,    # 桌面 Firefox 允许 2 次
            'edge': 1,       # 桌面 Edge 允许 2 次
            'safari': 1,     # 桌面 Safari 允许 2 次
            'default': 1     # 其他桌面浏览器默认 2 次
        },
        'download_tool': {
            'default': 1     # 下载工具严格限制 0 次
        },
        'unknown': {
            'default': 1     # 未知类型严格限制 1 次
        }
    }

    # 访问窗口 TTL（不同浏览器类型）
    M3U8_ACCESS_WINDOW_TTL = {
        'mobile_browser': 3 * 60,    # 移动浏览器 3 分钟窗口
        'desktop_browser': 2 * 60,   # 桌面浏览器 2 分钟窗口
        'download_tool': 1 * 60,     # 下载工具 1 分钟窗口
        'unknown': 1 * 60            # 未知类型 1 分钟窗口
    }
    
    # 兼容性开关
    ENABLE_BROWSER_ADAPTIVE_ACCESS = True  # 启用基于浏览器的自适应访问控制
    ENABLE_DETAILED_ACCESS_LOGGING = False  # 启用详细访问日志
    
    
    # 缓存配置
    M3U8_CACHE_TTL = 0  # .m3u8文件：禁用缓存
    TS_CACHE_TTL = 5 * 60  # .ts文件：5分钟缓存
    STATIC_CACHE_TTL = 60 * 60  # 静态文件：1小时缓存
    DEFAULT_CACHE_TTL = 10 * 60  # 其他文件：10分钟缓存
    FORCE_NO_CACHE_M3U8 = True  # 强制禁用.m3u8缓存


    # Cookie 配置
    COOKIE_SECURE = False  # HTTP环境下设为False
    COOKIE_HTTPONLY = True
    COOKIE_SAMESITE = "Lax"
    
    # 性能优化开关 - 已在上面根据性能优化器配置
    # ENABLE_REQUEST_DEDUPLICATION 等已经设置
    ENABLE_GZIP_COMPRESSION = True
    
    # === 流量收集器配置 ===
    TRAFFIC_COLLECTOR_ENABLED = True
    TRAFFIC_REPORT_URL = "https://v.yuelk.com/pyvideo2/api/traffic/report"  # 修改为您的实际URL
    TRAFFIC_API_KEY = "RosZ7eXV8dpDuouXGfhWp9N6yre2DBBnbRMcruTXLGwSxwgGH98ihoNG"  # 修改为您的实际API密钥，或设为None
    TRAFFIC_MIN_BYTES_THRESHOLD = 1024 * 1024  # 1MB门槛
    TRAFFIC_REPORT_INTERVAL = 10  # 5分钟上报间隔


    # 其他配置
    SECRET_KEY = b"super_secret_key_change_this"
    CORS_ALLOW_ORIGIN = "https://v.yuelk.com"
    CORS_ALLOW_ORIGIN2 = "https://v-upload.yuelk.com"
    SESSION_COOKIE_NAME = "session_id_fileserver"
    BACKEND_HOST = "127.0.0.1"
    BACKEND_PORT = 27804
    BACKEND_USE_HTTPS = False  # 启用HTTPS后端代理
    BACKEND_SSL_VERIFY = False  # 忽略SSL证书验证（用于自签名证书或测试环境）
    PROXY_HOST_HEADER = "edgecdn2-tc.yuelk.com"

config = OptimizedConfig()

# 全局流量收集器实例
traffic_collector = None


# 兼容性配置
SECRET_KEY = config.SECRET_KEY
TOKEN_CACHE_TTL = config.SESSION_TTL
CORS_ALLOW_ORIGIN = config.CORS_ALLOW_ORIGIN
CORS_ALLOW_ORIGIN2 = config.CORS_ALLOW_ORIGIN2
SESSION_COOKIE_NAME = config.SESSION_COOKIE_NAME

# === 配置日志 ===
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] [PID:%(process)d] %(message)s',
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(
                filename=os.path.join(log_dir, 'proxy_optimized.log'),
                maxBytes=10*1024*1024,  # 10MB
                backupCount=10,
                encoding='utf-8'
            )
        ]
    )
    return logging.getLogger(__name__)

base_logger = setup_logging()

# === HTTP 客户端管理器（性能优化核心）===
# === 请求去重管理器 ===
class RequestDeduplicator:
    def __init__(self):
        self._pending_requests: Dict[str, asyncio.Task] = {}
        self._cleanup_interval = 300  # 5分钟清理一次
        self._last_cleanup = time.time()
    
    def _cleanup_expired(self):
        """清理过期的待处理请求"""
        current_time = time.time()
        if current_time - self._last_cleanup > self._cleanup_interval:
            expired_keys = []
            for key, task in self._pending_requests.items():
                if task.done():
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._pending_requests.pop(key, None)
            
            self._last_cleanup = current_time
            if expired_keys:
                base_logger.debug(f"清理了 {len(expired_keys)} 个过期请求")
    
    async def get_or_wait(self, key: str, coro_func):
        """获取或等待请求结果"""
        self._cleanup_expired()
        
        if key in self._pending_requests:
            task = self._pending_requests[key]
            if not task.done():
                # 等待现有请求完成
                try:
                    return await task
                except Exception:
                    # 如果任务失败，移除并重新创建
                    self._pending_requests.pop(key, None)
        
        # 创建新请求
        task = asyncio.create_task(coro_func())
        self._pending_requests[key] = task
        
        try:
            result = await task
            return result
        finally:
            # 请求完成后保留一段时间供其他相同请求使用
            pass

request_deduplicator = RequestDeduplicator()

# === Redis 连接池管理（修复版）===
class RedisManager:
    def __init__(self):
        self.pool = None
        self._clients = weakref.WeakSet()
    
    async def initialize(self):
        """初始化 Redis 连接池"""
        try:
            # 创建连接池配置，根据系统支持情况决定是否启用keepalive
            pool_kwargs = {
                'host': config.REDIS_HOST,
                'port': config.REDIS_PORT,
                'db': config.REDIS_DB,
                'password': config.REDIS_PASSWORD,
                'decode_responses': True,
                'max_connections': config.REDIS_POOL_SIZE,
                'retry_on_timeout': True,
                'retry_on_error': [ConnectionError, TimeoutError],
                'health_check_interval': 30
            }
            
            # 尝试启用socket keepalive（如果支持的话）
            if config.REDIS_SOCKET_KEEPALIVE:
                try:
                    pool_kwargs['socket_keepalive'] = True
                    # 只在Linux系统上设置keepalive选项
                    if hasattr(socket, 'TCP_KEEPIDLE'):
                        pool_kwargs['socket_keepalive_options'] = config.REDIS_SOCKET_KEEPALIVE_OPTIONS
                except Exception as e:
                    base_logger.warning(f"Socket keepalive配置失败，将使用默认配置: {str(e)}")
                    # 如果keepalive配置失败，移除相关配置
                    pool_kwargs.pop('socket_keepalive', None)
                    pool_kwargs.pop('socket_keepalive_options', None)
            
            self.pool = redis_async.ConnectionPool(**pool_kwargs)
            
            # 测试连接
            redis_client = self.get_client()
            await redis_client.ping()
            base_logger.info(f"Redis 连接池初始化成功，连接数: {config.REDIS_POOL_SIZE} [PID: {os.getpid()}]")
            
        except Exception as e:
            base_logger.error(f"Redis 连接池初始化失败 [PID: {os.getpid()}]: {str(e)}")
            # 如果初始化失败，尝试使用简化配置
            try:
                base_logger.info("尝试使用简化Redis配置重新连接...")
                self.pool = redis_async.ConnectionPool(
                    host=config.REDIS_HOST,
                    port=config.REDIS_PORT,
                    db=config.REDIS_DB,
                    password=config.REDIS_PASSWORD,
                    decode_responses=True,
                    max_connections=50,  # 减少连接数
                    retry_on_timeout=True
                )
                redis_client = self.get_client()
                await redis_client.ping()
                base_logger.info(f"Redis 连接池简化配置初始化成功 [PID: {os.getpid()}]")
            except Exception as e2:
                base_logger.error(f"Redis 连接池简化配置也失败 [PID: {os.getpid()}]: {str(e2)}")
                raise e2
    
    def get_client(self):
        """获取 Redis 客户端实例"""
        if self.pool is None:
            raise RuntimeError("Redis 连接池未初始化")
        client = redis_async.Redis(connection_pool=self.pool)
        self._clients.add(client)
        return client
    
    async def close(self):
        """关闭 Redis 连接池"""
        if self.pool:
            await self.pool.disconnect()
            base_logger.info(f"Redis 连接池已关闭 [PID: {os.getpid()}]")

redis_manager = RedisManager()

# === 批量 Redis 操作（性能优化）===
# === 修复的批量 Redis 操作（性能优化）===
async def batch_redis_operations(redis_client, operations: List[Tuple]) -> List[Any]:
    """批量执行Redis操作 - 修复版"""
    if not config.ENABLE_REDIS_PIPELINE or len(operations) <= 1:
        # 如果只有一个操作或禁用pipeline，直接执行
        results = []
        for op in operations:
            op_type, key, *args = op
            try:
                if op_type == 'get':
                    result = await redis_client.get(key)
                elif op_type == 'set':
                    if len(args) >= 2 and args[1] == 'EX':
                        # 带过期时间的set操作: ('set', key, value, 'EX', ttl)
                        result = await redis_client.set(key, args[0], ex=args[2])
                    elif len(args) >= 2 and args[1] == 'NX':
                        # 带NX标志的set操作: ('set', key, value, 'NX', True)
                        result = await redis_client.set(key, args[0], nx=True)
                    elif len(args) >= 4 and args[1] == 'EX' and args[3] == 'NX':
                        # 带过期时间和NX的set操作: ('set', key, value, 'EX', ttl, 'NX', True)
                        result = await redis_client.set(key, args[0], ex=args[2], nx=True)
                    else:
                        # 普通set操作
                        result = await redis_client.set(key, args[0])
                elif op_type == 'expire':
                    result = await redis_client.expire(key, args[0])
                elif op_type == 'ttl':
                    result = await redis_client.ttl(key)
                else:
                    result = None
                results.append(result)
            except Exception as e:
                base_logger.error(f"Redis操作失败: {op_type} {key} - {str(e)}")
                results.append(None)
        return results
    
    # 使用pipeline批量执行
    try:
        pipe = redis_client.pipeline()
        for op_type, key, *args in operations:
            if op_type == 'get':
                pipe.get(key)
            elif op_type == 'set':
                if len(args) >= 2 and args[1] == 'EX':
                    # 带过期时间的set操作
                    pipe.set(key, args[0], ex=args[2])
                elif len(args) >= 2 and args[1] == 'NX':
                    # 带NX标志的set操作
                    pipe.set(key, args[0], nx=True)
                elif len(args) >= 4 and args[1] == 'EX' and args[3] == 'NX':
                    # 带过期时间和NX的set操作
                    pipe.set(key, args[0], ex=args[2], nx=True)
                else:
                    # 普通set操作
                    pipe.set(key, args[0])
            elif op_type == 'expire':
                pipe.expire(key, args[0])
            elif op_type == 'ttl':
                pipe.ttl(key)
        
        return await pipe.execute()
    except Exception as e:
        base_logger.error(f"Redis pipeline操作失败: {str(e)}")
        # 如果pipeline失败，回退到单个操作（避免递归）
        results = []
        for op in operations:
            op_type, key, *args = op
            try:
                if op_type == 'get':
                    result = await redis_client.get(key)
                elif op_type == 'set':
                    if len(args) >= 2 and args[1] == 'EX':
                        result = await redis_client.set(key, args[0], ex=args[2])
                    elif len(args) >= 2 and args[1] == 'NX':
                        result = await redis_client.set(key, args[0], nx=True)
                    elif len(args) >= 4 and args[1] == 'EX' and args[3] == 'NX':
                        result = await redis_client.set(key, args[0], ex=args[2], nx=True)
                    else:
                        result = await redis_client.set(key, args[0])
                elif op_type == 'expire':
                    result = await redis_client.expire(key, args[0])
                elif op_type == 'ttl':
                    result = await redis_client.ttl(key)
                else:
                    result = None
                results.append(result)
            except Exception as e2:
                base_logger.error(f"Redis单个操作失败: {op_type} {key} - {str(e2)}")
                results.append(None)
        return results



# === 获取客户端真实IP ===
def get_client_ip(request):
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return getattr(request, 'remote', 'unknown') or 'unknown'

# === 提取关键路径 ===
def extract_match_key(path: str) -> str:
    try:
        # Normalize path and split into components
        path = path.rstrip('/')
        parts = path.split('/')
        
        # Look for a date pattern (YYYY-MM-DD) in the path
        date_pattern = re.compile(r'\d{4}-\d{2}-\d{2}')
        date_index = -1
        for i, part in enumerate(parts):
            if date_pattern.match(part):
                date_index = i
                break
        
        # If date found, try to get the folder immediately following it
        if date_index != -1 and date_index + 1 < len(parts):
            return parts[date_index + 1]
        
        # Fallback: return the folder before the filename
        return os.path.basename(os.path.dirname(path))
    
    except Exception as e:
        base_logger.error(f"Failed to extract match key from path {path}: {str(e)}")
        return ""


# === HMAC 签名校验（优化版）===
def validate_token(uid: str, path: str, expires: str, token: str, logger) -> bool:
    try:
        current_time = int(time.time())
        expire_time = int(expires)
        if current_time > expire_time:
            logger.debug(f"Token expired: current_time={current_time}, expires={expire_time}")
            return False
        
        msg = f"{uid}:{path}:{expires}".encode()
        expected = hmac.new(SECRET_KEY, msg, hashlib.sha256).digest()
        expected_token = base64.urlsafe_b64encode(expected).decode().rstrip('=')
        is_valid = hmac.compare_digest(expected_token, token)
        
        logger.debug(f"HMAC validation: uid={uid}, path={path}, expires={expires}, valid={is_valid}")
        return is_valid
    except (ValueError, TypeError) as e:
        logger.error(f"HMAC validation error: {str(e)}")
        return False

# === 缓存控制函数（优化版）===
def get_cache_headers(path: str, file_type: str) -> dict:
    """根据文件类型返回相应的缓存头"""
    headers = {}
    return headers

# === Session Cookie 创建函数 ===
def create_session_cookie(session_id: str) -> str:
    """创建session cookie字符串"""
    cookie_parts = [
        f"{config.SESSION_COOKIE_NAME}={session_id}",
        "Path=/",
        f"Max-Age={config.SESSION_TTL}"
    ]
    
    if config.COOKIE_HTTPONLY:
        cookie_parts.append("HttpOnly")
    
    if config.COOKIE_SECURE:
        cookie_parts.append("Secure")
    
    if config.COOKIE_SAMESITE:
        cookie_parts.append(f"SameSite={config.COOKIE_SAMESITE}")
    
    return "; ".join(cookie_parts)

# === Session 管理（优化版）===


async def get_or_validate_session_by_ip_ua(uid: Optional[str], client_ip: str, user_agent: str, path: str, logger) -> Tuple[Optional[str], bool, Optional[str]]:
    redis_client = redis_manager.get_client()
    try:
        key_path = extract_match_key(path)
        if not key_path:
            logger.debug(f"无效的 key_path 提取: path={path}, user_agent={user_agent}")
            return None, False, None
        
        ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        effective_uid = uid
        
        # 如果提供了 UID（例如 .m3u8 请求），尝试精确匹配
        if uid:
            session_key = f"ip_ua_session:{client_ip}:{ua_hash}:{uid}:{key_path}"
            existing_session_id = await redis_client.get(session_key)
            
            if existing_session_id:
                session_data = await validate_session_internal(redis_client, existing_session_id, client_ip, user_agent, logger)
                if session_data and session_data.get("uid") == uid and session_data.get("key_path") == key_path:
                    if await extend_session(redis_client, existing_session_id, session_data, logger):
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
                    session_data = await validate_session_internal(redis_client, session_id, client_ip, user_agent, logger)
                    if session_data and session_data.get("key_path") == key_path:
                        last_activity = session_data.get("last_activity", 0)
                        if last_activity > latest_timestamp:
                            latest_timestamp = last_activity
                            latest_session_id = session_id
                            latest_session_data = session_data
            
            if latest_session_id:
                effective_uid = latest_session_data.get("uid")
                if await extend_session(redis_client, latest_session_id, latest_session_data, logger):
                    logger.debug(f"复用 IP+UA+key_path 会话: {latest_session_id}, ip={client_ip}, uid={effective_uid}")
                    return latest_session_id, False, effective_uid
        
        # 仅当提供了 UID 时创建新会话
        if not uid:
            logger.debug(f"未提供 UID 且未找到匹配会话: IP={client_ip}, UA hash={ua_hash}, key_path={key_path}")
            return None, False, None
        
        # 创建新会话
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        session_data = {
            "uid": uid,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "path": path,
            "key_path": key_path,
            "created_at": int(now.timestamp()),
            "last_activity": int(now.timestamp()),
            "worker_pid": os.getpid(),
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



async def validate_session_internal(redis_client, session_id: str, client_ip: str, user_agent: str, logger) -> Optional[dict]:
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

# === 修复的 Session 扩展函数 ===
async def extend_session(redis_client, session_id: str, session_data: dict, logger) -> bool:
    """延长session有效期并更新活动时间 - 修复版"""
    try:
        now = datetime.utcnow()
        session_data["last_activity"] = int(now.timestamp())
        session_data["access_count"] = session_data.get("access_count", 0) + 1
        
        # 修复：正确的操作格式
        operations = [
            ('set', f"session:{session_id}", json.dumps(session_data), 'EX', config.SESSION_TTL),
            ('expire', f"user_active_session:{session_data['uid']}:{session_data['client_ip']}", config.USER_SESSION_TTL)
        ]
        
        results = await batch_redis_operations(redis_client, operations)
        
        logger.debug(f"延长session有效期: {session_id}, ttl={config.SESSION_TTL}s")
        return results[0] is not None  # 只检查第一个set操作的结果
    except Exception as e:
        logger.error(f"延长session失败: {str(e)}")
        return False



# === 改进的 session 创建函数（优化版）===
async def get_or_create_session(uid: str, client_ip: str, user_agent: str, path: str, logger, existing_session_id: str = None) -> Tuple[Optional[str], bool]:
    """获取或创建session，返回 (session_id, is_new_session) - 修复版"""
    redis_client = redis_manager.get_client()
    try:
        # 如果有现有session，先验证并延期
        if existing_session_id:
            session_data = await validate_session_internal(redis_client, existing_session_id, client_ip, user_agent, logger)
            if session_data and session_data.get("uid") == uid:
                if await extend_session(redis_client, existing_session_id, session_data, logger):
                    logger.debug(f"复用现有session: {existing_session_id}, worker_pid={os.getpid()}")
                    return existing_session_id, False
        
        # 检查用户是否已有活跃session
        user_session_key = f"user_active_session:{uid}:{client_ip}"
        existing_user_session = await redis_client.get(user_session_key)
        
        if existing_user_session:
            session_data = await validate_session_internal(redis_client, existing_user_session, client_ip, user_agent, logger)
            if session_data:
                if await extend_session(redis_client, existing_user_session, session_data, logger):
                    logger.debug(f"复用用户已有session: {existing_user_session}, worker_pid={os.getpid()}")
                    return existing_user_session, False
        
        # 创建新session
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        session_data = {
            "uid": uid,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "path": path,
            "created_at": int(now.timestamp()),
            "last_activity": int(now.timestamp()),
            "worker_pid": os.getpid(),
            "access_count": 1
        }
        
        # 修复：正确的批量Redis操作格式
        operations = [
            ('set', f"session:{session_id}", json.dumps(session_data), 'EX', config.SESSION_TTL),
            ('set', user_session_key, session_id, 'EX', config.USER_SESSION_TTL)
        ]
        
        results = await batch_redis_operations(redis_client, operations)
        
        if results[0] is not None:  # 检查第一个set操作是否成功
            logger.info(f"创建新session: session_id={session_id}, uid={uid}, ttl={config.SESSION_TTL}s, worker_pid={os.getpid()}")
            return session_id, True
        else:
            logger.error(f"Session创建失败: {session_id}")
            return None, False
        
    except Exception as e:
        logger.error(f"Session操作失败: {str(e)}")
        return None, False


# === 验证会话（兼容性保留）===
async def validate_session(session_id: str, client_ip: str, user_agent: str, logger) -> Optional[dict]:
    redis_client = redis_manager.get_client()
    try:
        return await validate_session_internal(redis_client, session_id, client_ip, user_agent, logger)
    except Exception as e:
        logger.error(f"Failed to validate session {session_id}: {str(e)}")
        return None


# === 增强的 M3U8 访问控制函数 ===
# === 增强的 M3U8 访问控制函数（修复版）===
async def check_m3u8_access_count_adaptive(uid: str, full_url: str, client_ip: str, user_agent: str, logger) -> Tuple[bool, Dict[str, Any]]:
    """
    基于浏览器类型的自适应 M3U8 访问次数检查 - 修复版
    
    返回: (is_allowed, access_info)
    """
    redis_client = redis_manager.get_client()
    
    try:
        # 检测浏览器类型
        browser_type, browser_name, suggested_max_count = BrowserDetector.detect_browser_type(user_agent)
        
        # 调试信息记录
        if config.ENABLE_DETAILED_ACCESS_LOGGING:
            debug_info = BrowserDetector.debug_detection(user_agent)
            logger.info(f"浏览器检测调试: uid={uid}, user_agent='{user_agent}', "
                       f"detected={browser_type}/{browser_name}, debug_info={json.dumps(debug_info, indent=2)}")
        
        # 获取配置的访问次数限制
        if config.ENABLE_BROWSER_ADAPTIVE_ACCESS:
            access_limits = config.M3U8_ACCESS_LIMITS.get(browser_type, {})
            max_access_count = access_limits.get(browser_name, access_limits.get('default', suggested_max_count))
            access_window_ttl = config.M3U8_ACCESS_WINDOW_TTL.get(browser_type, 60)
        else:
            # 向后兼容：使用原始配置
            max_access_count = config.M3U8_DEFAULT_MAX_ACCESS_COUNT
            access_window_ttl = config.M3U8_SINGLE_USE_TTL
        
        # 生成请求标识
        request_identifier = f"{uid}:{full_url}:{client_ip}"
        request_hash = hashlib.sha256(request_identifier.encode()).hexdigest()
        redis_key = f"m3u8_access_count_v2:{request_hash}"
        
        # 详细日志记录
        logger.info(f"M3U8访问检查: uid={uid}, browser_type={browser_type}, browser_name={browser_name}, "
                   f"max_count={max_access_count}, window_ttl={access_window_ttl}s, hash={request_hash[:16]}...")
        
        # 使用Redis原子操作递增计数器
        current_count = await redis_client.incr(redis_key)
        
        # 如果是第一次访问，设置过期时间
        if current_count == 1:
            await redis_client.expire(redis_key, access_window_ttl)
            logger.info(f"M3U8首次访问: uid={uid}, browser={browser_name}, hash={request_hash[:16]}..., worker_pid={os.getpid()}")
            
            access_info = {
                "browser_type": browser_type,
                "browser_name": browser_name,
                "current_count": current_count,
                "max_count": max_access_count,
                "window_ttl": access_window_ttl,
                "remaining_count": max_access_count - current_count,
                "is_first_access": True,
                "user_agent": user_agent[:100] + "..." if len(user_agent) > 100 else user_agent  # 截断长UA
            }
            return True, access_info
        
        # 检查是否超过最大访问次数
        if current_count <= max_access_count:
            remaining_ttl = await redis_client.ttl(redis_key)
            logger.info(f"M3U8访问允许: uid={uid}, browser={browser_name}, count={current_count}/{max_access_count}, "
                       f"remaining_ttl={remaining_ttl}s, worker_pid={os.getpid()}")
            
            access_info = {
                "browser_type": browser_type,
                "browser_name": browser_name,
                "current_count": current_count,
                "max_count": max_access_count,
                "remaining_ttl": remaining_ttl,
                "remaining_count": max_access_count - current_count,
                "is_first_access": False,
                "user_agent": user_agent[:100] + "..." if len(user_agent) > 100 else user_agent
            }
            return True, access_info
        else:
            remaining_ttl = await redis_client.ttl(redis_key)
            logger.warning(f"M3U8访问次数超限: uid={uid}, browser={browser_name}, count={current_count}/{max_access_count}, "
                          f"remaining_ttl={remaining_ttl}s")
            
            access_info = {
                "browser_type": browser_type,
                "browser_name": browser_name,
                "current_count": current_count,
                "max_count": max_access_count,
                "remaining_ttl": remaining_ttl,
                "remaining_count": 0,
                "is_first_access": False,
                "exceeded": True,
                "user_agent": user_agent[:100] + "..." if len(user_agent) > 100 else user_agent
            }
            return False, access_info
            
    except Exception as e:
        logger.error(f"检查M3U8访问次数失败: {str(e)}")
        # 错误情况下，拒绝访问
        access_info = {
            "browser_type": "unknown",
            "browser_name": "unknown",
            "error": str(e),
            "user_agent": user_agent[:100] + "..." if len(user_agent) > 100 else user_agent
        }
        return False, access_info

# === 新增：浏览器检测调试接口 ===
async def browser_detection_debug(request):
    """浏览器检测调试接口"""
    try:
        user_agent = request.query.get("ua") or request.headers.get("User-Agent", "")
        
        if not user_agent:
            return web.json_response({
                "error": "请提供 User-Agent (通过 ?ua= 参数或 User-Agent 头)",
                "example": "/debug/browser?ua=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }, status=400)
        
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
            access_window_ttl = config.M3U8_SINGLE_USE_TTL
        
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
        
        return web.json_response(response_data)
        
    except Exception as e:
        return web.json_response({
            "error": f"浏览器检测调试失败: {str(e)}",
            "timestamp": int(time.time()),
            "worker_pid": os.getpid()
        }, status=500)
        

# 向后兼容的函数
async def check_m3u8_access_count(uid: str, full_url: str, client_ip: str, user_agent: str, logger) -> bool:
    """向后兼容的 M3U8 访问检查函数（不包含 user_agent 参数）"""
    is_allowed, _ = await check_m3u8_access_count_adaptive(uid, full_url, client_ip, user_agent, logger)
    return is_allowed

async def get_m3u8_access_count(uid: str, full_url: str, client_ip: str, logger) -> int:
    """仅获取M3U8访问次数，不递增计数器"""
    redis_client = redis_manager.get_client()
    try:
        request_identifier = f"{uid}:{full_url}:{client_ip}"
        request_hash = hashlib.sha256(request_identifier.encode()).hexdigest()
        # 使用新的key格式，但也兼容旧的key格式
        redis_key_v2 = f"m3u8_access_count_v2:{request_hash}"
        redis_key_v1 = f"m3u8_access_count:{request_hash}"
        
        # 首先检查新版本的key
        current_count = await redis_client.get(redis_key_v2)
        if current_count is None:
            # 如果新版本没有，检查旧版本
            current_count = await redis_client.get(redis_key_v1)
        
        count = int(current_count) if current_count else 0
        
        logger.debug(f"获取M3U8访问次数: uid={uid}, hash={request_hash[:16]}..., count={count}")
        return count
        
    except Exception as e:
        logger.error(f"获取M3U8访问次数失败: {str(e)}")
        return 0


async def get_m3u8_access_count(uid: str, full_url: str, client_ip: str, logger) -> int:
    """仅获取M3U8访问次数，不递增计数器"""
    redis_client = redis_manager.get_client()
    try:
        request_identifier = f"{uid}:{full_url}:{client_ip}"
        request_hash = hashlib.sha256(request_identifier.encode()).hexdigest()
        redis_key = f"m3u8_access_count:{request_hash}"
        
        current_count = await redis_client.get(redis_key)
        count = int(current_count) if current_count else 0
        
        logger.debug(f"获取M3U8访问次数: uid={uid}, hash={request_hash[:16]}..., count={count}")
        return count
        
    except Exception as e:
        logger.error(f"获取M3U8访问次数失败: {str(e)}")
        return 0


# === 改进的单次使用检查函数（优化版）===
async def check_single_use_m3u8(uid: str, full_url: str, client_ip: str, logger) -> bool:
    """修复版单次使用检查"""
    redis_client = redis_manager.get_client()
    try:
        request_identifier = f"{uid}:{full_url}:{client_ip}"
        request_hash = hashlib.sha256(request_identifier.encode()).hexdigest()
        redis_key = f"m3u8_single_use:{request_hash}"
        
        logger.debug(f"检查单次使用: uid={uid}, hash={request_hash[:16]}..., ttl={config.M3U8_SINGLE_USE_TTL}s")
        
        # 直接使用Redis客户端，避免批量操作的复杂性
        result = await redis_client.set(
            redis_key, 
            f"used_by_worker_{os.getpid()}_at_{int(time.time())}", 
            ex=config.M3U8_SINGLE_USE_TTL, 
            nx=True
        )
        
        if result:
            logger.info(f"标记.m3u8为已使用: uid={uid}, hash={request_hash[:16]}..., worker_pid={os.getpid()}")
            return True
        else:
            # 分别获取现有值和TTL，避免批量操作
            existing_value = await redis_client.get(redis_key)
            remaining_ttl = await redis_client.ttl(redis_key)
            logger.warning(f"单次使用.m3u8请求已被使用: uid={uid}, marked_by={existing_value}, remaining_ttl={remaining_ttl}s")
            return False
            
    except Exception as e:
        logger.error(f"检查单次使用.m3u8失败: {str(e)}")
        return False


# === 检查IP的关键路径访问权限（优化版）===

async def check_ip_key_path(client_ip: str, path: str, user_agent: str, logger) -> Tuple[bool, Optional[str]]:
    """简化的IP访问检查 - 统一使用CIDR方法"""
    redis_client = redis_manager.get_client()
    try:
        requested_key_path = extract_match_key(path)
        if not requested_key_path:
            logger.debug(f"无效的 key_path: path={path}, user_agent={user_agent}")
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
                        # 检查多路径支持
                        paths = data.get("paths", [])
                        if paths:
                            # 检查请求的路径是否在存储的路径列表中
                            for path_info in paths:
                                stored_path = path_info.get("key_path")
                                if stored_path and stored_path == requested_key_path:
                                    stored_key_path = stored_path
                                    stored_uid = data.get("uid")
                                    logger.info(f"✅ CIDR匹配成功: IP={client_ip} 匹配模式={matched_pattern}, 路径={stored_path}")
                                    break
                        else:
                            # 向后兼容：使用单一key_path
                            if data.get("key_path", "") == requested_key_path:
                                stored_key_path = data.get("key_path")
                                stored_uid = data.get("uid")
                                logger.info(f"✅ CIDR匹配成功: IP={client_ip} 匹配模式={matched_pattern}, 路径={stored_key_path}")
                        if stored_key_path:
                            break
                except json.JSONDecodeError:
                    continue
        
        if not stored_key_path:
            logger.warning(f"❌ IP访问被拒绝: IP={client_ip} 未找到匹配的CIDR模式, UA hash={ua_hash}, requested_key={requested_key_path}")
            return False, None
        
        # 检查访问权限（使用原始的substring匹配逻辑）
        if stored_key_path.lower() not in path.lower():
            logger.warning(f"❌ 访问被拒绝: IP={client_ip}, path={path}, requested_key={requested_key_path}, allowed_key={stored_key_path}")
            return False, stored_uid
        
        logger.info(f"✅ 访问允许: IP={client_ip}, path={path}, key_path={stored_key_path}, uid={stored_uid}")
        return True, stored_uid
        
    except Exception as e:
        logger.error(f"检查 key_path 失败: IP={client_ip}, path={path}, error={str(e)}")
        return False, None


async def session_debug(request):
    """Session and UID debug endpoint"""
    try:
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "unknown")
        session_id = request.cookies.get(SESSION_COOKIE_NAME) or request.headers.get("X-Session-ID")
        uid = request.query.get("uid")
        path = request.query.get("path", "")

        redis_client = redis_manager.get_client()
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
            session_data = await validate_session_internal(redis_client, session_id, client_ip, user_agent, base_logger)
            response_data["session_data"] = session_data
            response_data["session_valid"] = bool(session_data)

        # Check IP+UA session
        if uid and path:
            key_path = extract_match_key(path)
            session_key = f"ip_ua_session:{client_ip}:{hashlib.md5(user_agent.encode()).hexdigest()[:8]}:{uid}:{key_path}"
            ip_ua_session_id = await redis_client.get(session_key)
            response_data["ip_ua_session_key"] = session_key
            response_data["ip_ua_session_id"] = ip_ua_session_id
            
            if ip_ua_session_id:
                ip_ua_session_data = await redis_client.get(f"session:{ip_ua_session_id}")
                response_data["ip_ua_session_data"] = json.loads(ip_ua_session_data) if ip_ua_session_data else None

        # Check whitelist
        ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        redis_key = f"ip_ua_access:{client_ip}:{ua_hash}"
        whitelist_key_path = await redis_client.get(redis_key)
        response_data["whitelist"] = {
            "ip_ua_key": redis_key,
            "key_path": whitelist_key_path
        }

        return web.json_response(response_data)
        
    except Exception as e:
        return web.json_response({
            "error": f"Session debug failed: {str(e)}",
            "timestamp": int(time.time()),
            "worker_pid": os.getpid()
        }, status=500)

        
# CORS will be handled by aiohttp_cors library

# === 流式代理函数（性能优化核心）===
# === 增强的流式代理函数（核心修复）===
async def stream_proxy_response(remote_url: str, headers: Dict[str, str], request, logger, file_type: str = "default", uid: str = None, session_id: str = None) -> web.StreamResponse:
    """流式代理响应，增强错误处理和稳定性"""
    timeout = 30 if file_type == "m3u8" else 120
    global traffic_collector  # 添加这一行
    client_ip = get_client_ip(request)

    try:
        # 获取HTTP会话
        session = await http_client_manager.get_session()
        
        # 检查客户端连接状态
        if hasattr(request, 'transport') and request.transport is not None and request.transport.is_closing():
            logger.debug(f"客户端连接已关闭，停止代理请求: {remote_url}")
            return web.Response(status=499)  # Client Closed Request
        
        async with session.get(remote_url, headers=headers, timeout=timeout) as resp:
            # 检查响应状态
            if resp.status >= 400:
                logger.warning(f"后端返回错误状态 {resp.status}: {remote_url}")
                return web.Response(status=resp.status)
            
            # 设置响应头 - 排除CORS头以避免与aiohttp_cors库冲突
            excluded_headers = {
                "transfer-encoding", "content-encoding", "content-length", "connection",
                "access-control-allow-origin", "access-control-allow-methods", 
                "access-control-allow-headers", "access-control-allow-credentials",
                "access-control-max-age", "access-control-expose-headers"
            }
            proxy_headers = {
                k: v for k, v in resp.headers.items()
                if k.lower() not in excluded_headers
            }
            
            # 设置缓存策略
            cache_headers = get_cache_headers(remote_url, file_type)
            proxy_headers.update(cache_headers)
            
            # 创建流式响应
            try:
                if (config.ENABLE_RESPONSE_STREAMING and 
                    resp.content_length and 
                    resp.content_length > config.BUFFER_SIZE):
                    # 大文件使用流式传输
                    response = web.StreamResponse(
                        status=resp.status,
                        headers=proxy_headers
                    )
                    
                    try:
                        await response.prepare(request)
                    except Exception as prepare_error:
                        if ErrorHandler.is_client_disconnect_error(prepare_error):
                            logger.debug(f"客户端在准备响应时断开: {remote_url}")
                            return web.Response(status=499)
                        raise
                    
                    # 流式传输内容
                    bytes_transferred = 0
                    try:
                        async for chunk in resp.content.iter_chunked(config.STREAM_CHUNK_SIZE):
                            # 检查客户端连接状态
                            if (hasattr(request, 'transport') and 
                                request.transport is not None and 
                                request.transport.is_closing()):
                                logger.debug(f"客户端断开连接，停止传输: {remote_url}, 已传输: {bytes_transferred} bytes")
                                break
                            
                            try:
                                await response.write(chunk)
                                bytes_transferred += len(chunk)
                            except Exception as write_error:
                                if ErrorHandler.is_client_disconnect_error(write_error):
                                    logger.debug(f"客户端断开连接: {remote_url}, 已传输: {bytes_transferred} bytes")
                                    break  # 正常退出，不抛出异常
                                else:
                                    raise
                        
                        try:
                            await response.write_eof()
                        except Exception as eof_error:
                            if ErrorHandler.is_client_disconnect_error(eof_error):
                                logger.debug(f"客户端在写入EOF时断开: {remote_url}")
                            else:
                                logger.warning(f"写入EOF失败: {remote_url} - {str(eof_error)}")
                        
                        # === 添加流量记录 ===
                        if config.TRAFFIC_COLLECTOR_ENABLED and traffic_collector and uid and bytes_transferred > 0:
                            traffic_collector.record_traffic(
                                uid=uid,
                                bytes_transferred=bytes_transferred,
                                file_type=file_type,
                                client_ip=client_ip,
                                session_id=session_id
                            )
                        

                        
                        logger.debug(f"流式传输完成: {remote_url}, 传输字节: {bytes_transferred}, worker_pid={os.getpid()},[UID]={uid}")
                    except Exception as stream_error:
                        if ErrorHandler.is_client_disconnect_error(stream_error):
                            logger.debug(f"流式传输中客户端断开: {remote_url}, 已传输: {bytes_transferred} bytes")
                        else:
                            logger.error(f"流式传输错误: {remote_url} - {str(stream_error)}")
                            raise
                    
                    return response
                else:
                    # 小文件直接读取
                    try:
                        body = await resp.read()

                        # === 添加流量记录 ===
                        if config.TRAFFIC_COLLECTOR_ENABLED and traffic_collector and uid and len(body) > 0:
                            traffic_collector.record_traffic(
                                uid=uid,
                                bytes_transferred=len(body),
                                file_type=file_type,
                                client_ip=client_ip,
                                session_id=session_id
                            )

                        logger.debug(f"直接传输完成: {remote_url}, size={len(body)} bytes, worker_pid={os.getpid()}")
                        return web.Response(body=body, status=resp.status, headers=proxy_headers)
                    except Exception as read_error:
                        if ErrorHandler.is_client_disconnect_error(read_error):
                            logger.debug(f"客户端在读取时断开: {remote_url}")
                            return web.Response(status=499)
                        else:
                            raise
            
            except Exception as response_error:
                if ErrorHandler.is_client_disconnect_error(response_error):
                    logger.debug(f"客户端连接错误: {remote_url} - {str(response_error)}")
                    return web.Response(status=499)
                else:
                    raise
                    
    except Exception as e:
        # 错误分类处理
        if ErrorHandler.is_client_disconnect_error(e):
            if not ErrorHandler.should_suppress_logging(e):
                logger.debug(f"客户端断开连接: {remote_url} - {str(e)}")
            return web.Response(status=499)
        
        elif isinstance(e, asyncio.TimeoutError) or 'timeout' in str(e).lower():
            logger.warning(f"请求超时: {remote_url}")
            return web.Response(status=504, text="网关超时")
        
        else:
            # 其他错误
            logger.error(f"代理请求失败: {remote_url} - {str(e)}")
            return web.Response(status=502, text=f"代理失败: {str(e)}")


# === 主代理处理逻辑（优化版）===
# === 主代理处理逻辑（优化版）===
# In proxy_handler, modify the session validation and UID retrieval logic
async def proxy_handler(request):
    client_ip = get_client_ip(request)
    logger = ClientIPAdapter(base_logger, client_ip)

    # 获取请求参数
    uid = request.query.get("uid")
    expires = request.query.get("expires")
    token = request.query.get("token")
    path = request.match_info.get("path", "")
    key_path = extract_match_key(path)
    full_url = str(request.url)
    user_agent = request.headers.get("User-Agent", "unknown")
    session_id = request.cookies.get(SESSION_COOKIE_NAME) or request.headers.get("X-Session-ID")

    logger.debug(f"请求接收: method={request.method}, path={path}, key_path={key_path}, uid={uid}, session_id={session_id}, worker_pid={os.getpid()}")

    # 确定请求类型
    skip_validation_suffixes = ('.webp', '.php', '.js', '.css', '.ico', '.txt', '.woff', '.woff2', '.ttf', '.png', '.jpg', '.jpeg', '.gif', '.svg')
    skip_validation = path.lower().endswith(skip_validation_suffixes)
    is_m3u8 = path.lower().endswith('.m3u8')
    is_ts = path.lower().endswith('.ts')
    is_enc_key = path.lower().endswith('enc.key')

    # 确定缓存策略的文件类型
    if is_m3u8:
        file_type = "m3u8"
    elif is_ts:
        file_type = "ts"
    elif is_enc_key:
        file_type = "enc_key"
    elif path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.woff', '.woff2', '.ttf')):
        file_type = "static"
    else:
        file_type = "default"

    new_session_created = False
    validated_session_data = None
    effective_uid = None

    # 非跳过验证请求的验证逻辑
    if not skip_validation:
        # 1. 检查路径权限并从白名单获取 UID
        is_allowed, whitelist_uid = await check_ip_key_path(client_ip, path, user_agent, logger)
        if not is_allowed:
            logger.warning(f"IP {client_ip} 无权访问路径 {path}, key_path={key_path}")
            return web.Response(text="Access Denied 100020 path", status=403)
        
        # 2. 对于允许访问的enc.key文件，检查是否启用Safe Key Protect重定向
        if is_allowed and is_enc_key and config.SAFE_KEY_PROTECT_ENABLED:
            redirect_url = f"{config.SAFE_KEY_PROTECT_REDIRECT_BASE_URL}{path}"
            logger.info(f"🔐 Safe Key Protect重定向: IP={client_ip}, enc.key文件={path}, redirect_to={redirect_url}")
            
            # 创建重定向响应，让aiohttp_cors库自动处理CORS头
            redirect_headers = {
                'Location': redirect_url,
                'Cache-Control': 'no-cache, no-store, must-revalidate',  # 防止缓存问题
            }
            
            return web.Response(
                status=302,
                headers=redirect_headers
            )
        
        # 3. 尝试通过 IP+UA+key_path 获取会话（即使没有 UID）
        session_id, new_session_created, session_uid = await get_or_validate_session_by_ip_ua(uid, client_ip, user_agent, path, logger)
        if session_id:
            validated_session_data = await validate_session_internal(redis_manager.get_client(), session_id, client_ip, user_agent, logger)
            if validated_session_data:
                effective_uid = session_uid or validated_session_data.get("uid")
                logger.debug(f"找到会话: session_id={session_id}, uid={effective_uid}, key_path={key_path}")
        
        # 4. 如果没有会话 UID，使用白名单 UID 作为后备
        if not effective_uid and whitelist_uid:
            effective_uid = whitelist_uid
            logger.debug(f"使用白名单 UID={whitelist_uid} 对于 path={path}, key_path={key_path}")
        
        # 5. 处理 .m3u8 请求的严格验证
        if is_m3u8:
            if not effective_uid:
                logger.warning(f"无有效 UID 对于 .m3u8 请求: path={path}, key_path={key_path}")
                return web.Response(text="No valid UID for .m3u8 request", status=403)
            
            if not uid or not expires or not token:
                logger.warning(f".m3u8 请求缺少 HMAC 参数: path={path}, key_path={key_path}")
                return web.Response(text=".m3u8 request missing required parameters (uid, expires, token)", status=400)
            
            hmac_valid = validate_token(uid, path, expires, token, logger)
            if not hmac_valid:
                logger.warning(f".m3u8 请求令牌无效或已过期: path={path}, key_path={key_path}")
                return web.Response(text=".m3u8 request token invalid or expired hmac", status=403)
            
            if not await check_m3u8_access_count(effective_uid, full_url, client_ip, user_agent, logger):
                logger.warning(f"单次使用违规 .m3u8 路径: {path}, key_path={key_path}, uid={effective_uid}")
                return web.Response(text=f"Access Denied 100308 with uid:{effective_uid}", status=403)

    # 代理请求到后端服务器
    backend_scheme = "https" if config.BACKEND_USE_HTTPS else "http"
    remote_url = f"{backend_scheme}://{config.BACKEND_HOST}:{config.BACKEND_PORT}/{path}"
    headers = {
        "User-Agent": user_agent,
        "Host": config.PROXY_HOST_HEADER,
        "X-Forwarded-For": client_ip
    }

    # 添加原始请求头（如果需要）
    for header_name in ["Range", "If-Range", "If-Modified-Since", "If-None-Match"]:
        if header_name in request.headers:
            headers[header_name] = request.headers[header_name]

    try:
        # 使用有效的 UID 进行流代理
        response = await stream_proxy_response(remote_url, headers, request, logger, file_type, uid=effective_uid, session_id=session_id)
        
        # 仅在创建新会话时设置 cookie
        if new_session_created and session_id:
            response.headers["Set-Cookie"] = create_session_cookie(session_id)
            logger.info(f"设置新会话 cookie: {session_id}, ttl={config.SESSION_TTL}s")
        
        return response
        
    except Exception as e:
        if ErrorHandler.is_client_disconnect_error(e):
            if not ErrorHandler.should_suppress_logging(e):
                logger.debug(f"客户端断开连接: {remote_url} - {str(e)}")
            return web.Response(status=499)
        else:
            err_msg = str(e)
            logger.error(f"代理请求失败: {remote_url} - {err_msg}")
            return web.Response(text=f"Proxy failed: {err_msg}", status=502)
            

async def add_ip_whitelist(request):
    client_ip = get_client_ip(request)
    logger = ClientIPAdapter(base_logger, client_ip)

    try:
        # Validate API key
        api_key = request.headers.get("Authorization")
        if not api_key or api_key != "Bearer F2UkWEJZRBxC7":
            logger.warning("Whitelist addition failed: Invalid or missing API key")
            return web.json_response({"error": "Invalid or missing API key"}, status=403)

        # Parse request data
        data = await request.json()
        uid = data.get("uid")
        path = data.get("path")
        target_client_ip = data.get("clientIp")
        user_agent = data.get("UserAgent")

        if not uid or not path or not target_client_ip or not user_agent:
            logger.warning("Whitelist addition failed: Missing uid, path, clientIp, or UserAgent")
            return web.json_response({"error": "uid, path, clientIp, and userAgent are required"}, status=400)

        # Extract key path
        key_path = extract_match_key(path)
        if not key_path:
            logger.warning(f"Invalid key path extracted from {path}")
            return web.json_response({"error": "Invalid path format"}, status=400)

        # 标准化IP地址（自动转换为/24子网）
        if CIDRMatcher.is_valid_ip(target_client_ip) or CIDRMatcher.is_cidr_notation(target_client_ip):
            normalized_pattern = CIDRMatcher.normalize_cidr(target_client_ip)
            logger.info(f"已标准化IP模式: {target_client_ip} -> {normalized_pattern}")
        else:
            logger.warning(f"无效的IP模式: {target_client_ip}")
            return web.json_response({
                "error": f"Invalid IP address or CIDR: {target_client_ip}",
                "note": "Please provide a valid IP address or CIDR notation"
            }, status=400)

        # Store in Redis using unified CIDR approach
        redis_client = redis_manager.get_client()
        ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        current_time = int(time.time())
        
        # 统一使用CIDR键格式存储所有IP（包括单IP和CIDR）
        redis_key = f"ip_cidr_access:{normalized_pattern.replace('/', '_')}:{ua_hash}"
        
        # 构建数据结构，支持多路径存储
        whitelist_data = {
            "uid": uid,
            "key_path": key_path,
            "paths": [{"key_path": key_path, "created_at": current_time}],
            "ip_patterns": [normalized_pattern],
            "user_agent": user_agent,
            "created_at": current_time,
            "worker_pid": os.getpid()
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
                    
                    # 保持最多配置的路径数，移除最旧的（FIFO）
                    if len(existing_paths) > config.MAX_PATHS_PER_CIDR:
                        existing_paths.sort(key=lambda x: x.get("created_at", 0))
                        existing_paths = existing_paths[-config.MAX_PATHS_PER_CIDR:]
                    
                    existing_data["paths"] = existing_paths
                    existing_data["key_path"] = key_path  # 更新为最新路径
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
                # 旧格式数据，保持向后兼容
                merged_count = 0
                new_count = 1
        
        # 存储更新的数据
        await redis_client.set(redis_key, json.dumps(whitelist_data), ex=config.IP_ACCESS_TTL)
        
        # 生成CIDR示例用于调试
        cidr_examples = CIDRMatcher.expand_cidr_examples(normalized_pattern, 3)
        
        logger.info(f"存储IP模式成功: patterns=[{normalized_pattern}], ua_hash={ua_hash}, TTL={config.IP_ACCESS_TTL}s, 合并={merged_count}, 新建={new_count}")
        return web.json_response({
            "message": "CIDR whitelist added/updated successfully with unified storage",
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
            "worker_pid": os.getpid()
        }, status=200)
        
    except json.JSONDecodeError:
        logger.error("JSON parse error")
        return web.json_response({"error": "Invalid JSON data"}, status=400)
    except Exception as e:
        logger.error(f"add_ip_whitelist error: {str(e)}")
        return web.json_response({"error": f"Failed to add IP to whitelist: {str(e)}"}, status=500)


# === 简化的批量操作辅助函数 ===
async def simple_redis_get_multiple(redis_client, keys: List[str]) -> List[Any]:
    """简单的批量获取Redis值"""
    try:
        if len(keys) == 1:
            result = await redis_client.get(keys[0])
            return [result]
        
        # 使用mget进行批量获取
        return await redis_client.mget(keys)
    except Exception as e:
        base_logger.error(f"批量Redis获取失败: {str(e)}")
        # 回退到单个操作
        results = []
        for key in keys:
            try:
                result = await redis_client.get(key)
                results.append(result)
            except Exception:
                results.append(None)
        return results


# === 健康检查路由（优化版）===
async def health_check(request):
    global traffic_collector  # 添加这一行
    try:
        redis_client = redis_manager.get_client()
        start_time = time.time()
        await redis_client.ping()
        redis_latency = (time.time() - start_time) * 1000  # 毫秒
        
        # 获取连接池状态
        pool_status = {}
        if redis_manager.pool:
            pool_status = {
                "max_connections": redis_manager.pool.max_connections,
                "created_connections": getattr(redis_manager.pool, 'created_connections', 'N/A'),
            }
        
        # 获取流量收集器状态
        traffic_status = "disabled"
        if config.TRAFFIC_COLLECTOR_ENABLED:
            if traffic_collector:
                traffic_status = "running" if traffic_collector._running else "stopped"
            else:
                traffic_status = "not_initialized"

        return web.json_response({
            "status": "healthy",
            "timestamp": int(time.time()),
            "redis": {
                "status": "connected",
                "latency_ms": round(redis_latency, 2),
                "pool": pool_status
            },
            "http_client": {
                "status": "active" if http_client_manager.session and not http_client_manager.session.closed else "inactive"
            },
            "worker_pid": os.getpid(),
            "performance_optimization": {
                "uvloop_enabled": UVLOOP_AVAILABLE,
                "optimizer_enabled": PERFORMANCE_OPTIMIZER_ENABLED,
                "optimization_level": "high" if UVLOOP_AVAILABLE else "medium"
            },
            "config": {
                "session_ttl": config.SESSION_TTL,
                "m3u8_ttl": config.M3U8_SINGLE_USE_TTL,
                "user_session_ttl": config.USER_SESSION_TTL,
                "ip_access_ttl": config.IP_ACCESS_TTL,
                "m3u8_cache_disabled": config.FORCE_NO_CACHE_M3U8,
                "ts_cache_ttl": config.TS_CACHE_TTL,
                "streaming_enabled": config.ENABLE_RESPONSE_STREAMING,
                "parallel_validation": config.ENABLE_PARALLEL_VALIDATION,
                "redis_pipeline": config.ENABLE_REDIS_PIPELINE,
                "request_deduplication": config.ENABLE_REQUEST_DEDUPLICATION,
                "safe_key_protect_enabled": config.SAFE_KEY_PROTECT_ENABLED,
                "safe_key_protect_redirect_url": config.SAFE_KEY_PROTECT_REDIRECT_BASE_URL,
                "backend_use_https": config.BACKEND_USE_HTTPS,
                "backend_ssl_verify": config.BACKEND_SSL_VERIFY
            },
            "traffic_collector": {
                "enabled": config.TRAFFIC_COLLECTOR_ENABLED,
                "status": traffic_status,
                "report_url": config.TRAFFIC_REPORT_URL if config.TRAFFIC_COLLECTOR_ENABLED else None
            },
            "performance": {
                "stream_chunk_size": config.STREAM_CHUNK_SIZE,
                "buffer_size": config.BUFFER_SIZE,
                "http_connector_limit": config.HTTP_CONNECTOR_LIMIT,
                "redis_pool_size": config.REDIS_POOL_SIZE
            }
        })
    except Exception as e:
        return web.json_response({
            "status": "unhealthy",
            "timestamp": int(time.time()),
            "redis": {
                "status": "disconnected",
                "error": str(e)
            },
            "worker_pid": os.getpid()
        }, status=503)

# === 性能统计路由 ===
async def performance_stats(request):
    """性能统计接口"""
    try:
        redis_client = redis_manager.get_client()
        
        # 获取当前活跃session数量
        try:
            session_keys = await redis_client.keys("session:*")
            active_sessions = len(session_keys)
        except Exception:
            active_sessions = "N/A"
        
        # 获取活跃用户数量
        try:
            user_keys = await redis_client.keys("user_active_session:*")
            active_users = len(user_keys)
        except Exception:
            active_users = "N/A"
        
        # 获取m3u8使用记录数量
        try:
            m3u8_keys = await redis_client.keys("m3u8_single_use:*")
            m3u8_uses = len(m3u8_keys)
        except Exception:
            m3u8_uses = "N/A"
        
        # 获取IP访问记录数量
        try:
            ip_keys = await redis_client.keys("ip_access:*")
            ip_accesses = len(ip_keys)
        except Exception:
            ip_accesses = "N/A"
        
        response_data = {
            "timestamp": int(time.time()),
            "worker_pid": os.getpid(),
            "redis_stats": {
                "active_sessions": active_sessions,
                "active_users": active_users,
                "m3u8_single_uses": m3u8_uses,
                "ip_accesses": ip_accesses
            },
            "request_deduplicator": {
                "pending_requests": len(request_deduplicator._pending_requests) if hasattr(request_deduplicator, '_pending_requests') else 0
            },
            "system_info": {
                "python_version": sys.version,
                "process_id": os.getpid()
            }
        }
        
        # 添加性能优化器的指标（如果可用）
        if PERFORMANCE_OPTIMIZER_ENABLED:
            response_data["performance_optimizer"] = get_performance_status()
        
        return web.json_response(response_data)
        
    except Exception as e:
        return web.json_response({
            "error": f"获取性能统计失败: {str(e)}",
            "timestamp": int(time.time()),
            "worker_pid": os.getpid()
        }, status=500)

# === 应用初始化和清理钩子（修复版）===
async def init_app_on_startup(app):
    """应用启动时初始化所有组件"""
    global traffic_collector
    try:
        # 初始化Redis
        await redis_manager.initialize()
        
        # 初始化HTTP客户端
        await http_client_manager.initialize()

                # 初始化流量收集器
        if config.TRAFFIC_COLLECTOR_ENABLED:
            try:
                traffic_collector = await init_traffic_collector(
                    redis_manager=redis_manager,
                    http_client_manager=http_client_manager,
                    logger=base_logger,
                    report_url=config.TRAFFIC_REPORT_URL,
                    api_key=config.TRAFFIC_API_KEY
                )
                base_logger.info(f"📊 流量收集器初始化成功")
            except Exception as e:
                base_logger.error(f"❌ 流量收集器初始化失败: {str(e)}")
                # 不因为流量收集器失败而停止整个应用
                traffic_collector = None
        
        
        base_logger.info(f"🚀 优化版代理服务器启动完成 [PID: {os.getpid()}]")
        base_logger.info(f"配置信息: Session TTL: {config.SESSION_TTL}s, 流式传输: {config.ENABLE_RESPONSE_STREAMING}, 并行验证: {config.ENABLE_PARALLEL_VALIDATION}")
        
    except Exception as e:
        base_logger.error(f"应用启动失败 [PID: {os.getpid()}]: {str(e)}")
        raise


async def probe_backend_file(request):
    """
    无认证探测后端文件是否可访问
    URL: /probe/backend?path=/xxx/yyy.ts
    """
    try:
        path = request.query.get("path", "")
        if not path or ".." in path:
            return web.json_response({"status": "error", "reason": "invalid_path"}, status=400)

        # 路径拼接和 proxy_handler 保持一致！
        backend_scheme = "https" if config.BACKEND_USE_HTTPS else "http"
        backend_url = f"{backend_scheme}://{config.BACKEND_HOST}:{config.BACKEND_PORT}{path if path.startswith('/') else '/' + path}"

        # headers要和proxy一致
        user_agent = request.headers.get("User-Agent", "ProbeAgent/1.0")
        client_ip = get_client_ip(request)
        headers = {
            "User-Agent": user_agent,
            "Host": config.PROXY_HOST_HEADER,
            "X-Forwarded-For": client_ip
        }

        # 可选：Range等头
        for header_name in ["Range", "If-Range", "If-Modified-Since", "If-None-Match"]:
            if header_name in request.headers:
                headers[header_name] = request.headers[header_name]

        # log实际请求的URL和headers
        base_logger.info(f"[probe_backend_file] backend_url={backend_url}, headers={headers}")

        session = await http_client_manager.get_session()
        try:
            async with session.get(backend_url, headers=headers, timeout=10) as resp:
                status = resp.status
                result = {
                    "status": "ok" if status == 200 else "fail",
                    "backend_status": status,
                    "reason": resp.reason,
                    "content_type": resp.headers.get("Content-Type", ""),
                    "backend_url": backend_url
                }
                return web.json_response(result, status=200)
        except Exception as e:
            return web.json_response({
                "status": "error", 
                "reason": f"backend_unreachable: {str(e)}",
                "backend_url": backend_url
            }, status=502)
    except Exception as e:
        return web.json_response({
            "status": "error",
            "reason": f"internal_error: {str(e)}"
        }, status=500)


# === CIDR 调试接口 ===
async def cidr_debug(request):
    """CIDR匹配调试接口"""
    try:
        test_ip = request.query.get("ip", "")
        test_cidr = request.query.get("cidr", "")
        
        if not test_ip:
            return web.json_response({
                "error": "请提供测试IP (通过 ?ip= 参数)",
                "example": "/debug/cidr?ip=192.168.1.100&cidr=192.168.1.0/24"
            }, status=400)
        
        response_data = {
            "test_ip": test_ip,
            "is_valid_ip": CIDRMatcher.is_valid_ip(test_ip),
            "timestamp": int(time.time()),
            "worker_pid": os.getpid()
        }
        
        if test_cidr:
            response_data.update({
                "test_cidr": test_cidr,
                "is_valid_cidr": CIDRMatcher.is_cidr_notation(test_cidr),
                "ip_in_cidr": CIDRMatcher.ip_in_cidr(test_ip, test_cidr) if CIDRMatcher.is_cidr_notation(test_cidr) else False,
                "normalized_cidr": CIDRMatcher.normalize_cidr(test_cidr),
                "cidr_examples": CIDRMatcher.expand_cidr_examples(test_cidr, 5) if CIDRMatcher.is_cidr_notation(test_cidr) else []
            })
        
        # 测试多个常见CIDR模式
        common_patterns = [
            test_ip,  # 精确匹配
            CIDRMatcher.normalize_cidr(test_ip),  # 转换为/32
            "192.168.1.0/24",  # 常见内网CIDR
            "10.0.0.0/8",      # 另一个内网CIDR
            "172.16.0.0/12"    # 第三个内网CIDR
        ]
        
        pattern_tests = {}
        for pattern in common_patterns:
            if CIDRMatcher.is_valid_ip(test_ip):
                pattern_tests[pattern] = {
                    "is_cidr": CIDRMatcher.is_cidr_notation(pattern),
                    "matches": CIDRMatcher.ip_in_cidr(test_ip, pattern) if CIDRMatcher.is_cidr_notation(pattern) else (test_ip == pattern)
                }
        
        response_data["pattern_tests"] = pattern_tests
        
        return web.json_response(response_data)
        
    except Exception as e:
        return web.json_response({
            "error": f"CIDR调试失败: {str(e)}",
            "timestamp": int(time.time()),
            "worker_pid": os.getpid()
        }, status=500)


# === IP白名单调试接口 ===  
async def ip_whitelist_debug(request):
    """IP白名单调试接口"""
    try:
        client_ip = get_client_ip(request)
        test_ip = request.query.get("ip", client_ip)
        user_agent = request.headers.get("User-Agent", "unknown")
        test_path = request.query.get("path", "/test/path")
        
        logger = ClientIPAdapter(base_logger, test_ip)
        
        # 测试IP白名单检查
        is_allowed, stored_uid = await check_ip_key_path(test_ip, test_path, user_agent, logger)
        
        ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        
        # 查找相关的Redis键（包括新的键格式）
        redis_client = redis_manager.get_client()
        search_patterns = [
            f"ip_ua_access:{test_ip}:{ua_hash}",
            f"ip_ua_access:{test_ip}:{ua_hash}:*",  # 新格式：包含路径哈希
            f"ip_cidr_access:*:{ua_hash}",
            f"ip_cidr_access:*:{ua_hash}:*",  # 新格式：包含路径哈希
            f"ip_broad_cidr:*:{ua_hash}",  # 新格式：广泛CIDR匹配
            f"ip_whitelist_index:{ua_hash}:*",
            f"ip_access:{test_ip}"
        ]
        
        found_keys = {}
        for pattern in search_patterns:
            keys = await redis_client.keys(pattern)
            if keys:
                found_keys[pattern] = []
                for key in keys:
                    data = await redis_client.get(key)
                    try:
                        parsed_data = json.loads(data) if data else None
                    except json.JSONDecodeError:
                        parsed_data = data
                    found_keys[pattern].append({
                        "key": key,
                        "data": parsed_data
                    })
        
        response_data = {
            "test_ip": test_ip,
            "test_path": test_path,
            "ua_hash": ua_hash,
            "is_allowed": is_allowed,
            "stored_uid": stored_uid,
            "key_path": extract_match_key(test_path),
            "found_redis_keys": found_keys,
            "cidr_info": {
                "is_valid_ip": CIDRMatcher.is_valid_ip(test_ip),
                "normalized": CIDRMatcher.normalize_cidr(test_ip)
            },
            "timestamp": int(time.time()),
            "worker_pid": os.getpid()
        }
        
        return web.json_response(response_data)
        
    except Exception as e:
        return web.json_response({
            "error": f"IP白名单调试失败: {str(e)}",
            "timestamp": int(time.time()),
            "worker_pid": os.getpid()
        }, status=500)
        


async def cleanup_app_on_shutdown(app):
    """应用关闭时清理所有组件"""
    global traffic_collector
    try:
        # 关闭HTTP客户端
        await http_client_manager.close()
        
        # 关闭Redis连接
        await redis_manager.close()
        
        # 停止流量收集器
        if traffic_collector:
            try:
                await traffic_collector.stop()
                base_logger.info("📊 流量收集器已停止")
            except Exception as e:
                base_logger.error(f"❌ 停止流量收集器失败: {str(e)}")

        base_logger.info(f"🛑 优化版代理服务器关闭完成 [PID: {os.getpid()}]")
        
    except Exception as e:
        base_logger.error(f"应用关闭失败 [PID: {os.getpid()}]: {str(e)}")


# === 流量统计接口 ===
async def traffic_stats(request):
    """流量收集器统计接口"""
    global traffic_collector
    try:
        if not config.TRAFFIC_COLLECTOR_ENABLED:
            return web.json_response({
                "status": "disabled",
                "message": "流量收集器未启用"
            })
        
        if not traffic_collector:
            return web.json_response({
                "status": "not_initialized",
                "message": "流量收集器未初始化"
            })
        
        status = traffic_collector.get_current_status()
        status["timestamp"] = int(time.time())
        
        return web.json_response(status)
        
    except Exception as e:
        return web.json_response({
            "error": f"获取流量统计失败: {str(e)}",
            "timestamp": int(time.time()),
            "worker_pid": os.getpid()
        }, status=500)


# === 监控面板路由 ===
async def monitor_dashboard(request):
    """Web监控面板"""
    try:
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        monitor_file = os.path.join(static_dir, "monitor.html")
        
        if os.path.exists(monitor_file):
            with open(monitor_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            return web.Response(text=html_content, content_type='text/html')
        else:
            return web.Response(text="监控面板文件未找到", status=404)
    except Exception as e:
        base_logger.error(f"加载监控面板失败: {str(e)}")
        return web.Response(text=f"加载监控面板失败: {str(e)}", status=500)


async def serve_static(request):
    """服务静态文件"""
    try:
        # 获取请求的文件路径
        file_path = request.match_info.get('path', '')
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        full_path = os.path.join(static_dir, file_path)
        
        # 安全检查：确保路径在static目录内
        if not os.path.abspath(full_path).startswith(os.path.abspath(static_dir)):
            return web.Response(text="禁止访问", status=403)
        
        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            return web.Response(text="文件未找到", status=404)
        
        # 确定content type
        content_type = 'text/plain'
        if file_path.endswith('.css'):
            content_type = 'text/css'
        elif file_path.endswith('.js'):
            content_type = 'application/javascript'
        elif file_path.endswith('.html'):
            content_type = 'text/html'
        elif file_path.endswith('.json'):
            content_type = 'application/json'
        elif file_path.endswith('.png'):
            content_type = 'image/png'
        elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
            content_type = 'image/jpeg'
        elif file_path.endswith('.svg'):
            content_type = 'image/svg+xml'
        
        with open(full_path, 'rb') as f:
            content = f.read()
        
        return web.Response(body=content, content_type=content_type)
        
    except Exception as e:
        base_logger.error(f"服务静态文件失败: {str(e)}")
        return web.Response(text=f"服务文件失败: {str(e)}", status=500)


# === 创建应用函数 (gunicorn 入口点) ===
app = create_app()

# === 直接运行支持 ===
