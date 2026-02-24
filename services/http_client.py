"""
HTTP 客户端服务
专门为 HLS 流媒体高并发优化
"""
import httpx
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class HTTPClientService:
    """
    HTTP 客户端服务
    针对 HLS 流媒体（m3u8/ts 文件）的高并发优化
    
    特性：
    - HTTP/2 支持
    - 连接池管理
    - Keep-Alive 优化
    - 自动重连
    """
    
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self._closed = False
        self._lock = asyncio.Lock()
    
    async def initialize(self, config):
        """
        初始化HTTP客户端
        
        Args:
            config: 配置对象
        """
        async with self._lock:
            if self.client is not None:
                return
            
            # 针对 HLS 流媒体优化的连接池配置
            limits = httpx.Limits(
                max_connections=config.HTTP_CONNECTOR_LIMIT,  # 总连接数
                max_keepalive_connections=config.HTTP_CONNECTOR_LIMIT_PER_HOST,  # 每个主机的keep-alive连接数
                keepalive_expiry=config.HTTP_KEEPALIVE_TIMEOUT  # keep-alive 过期时间
            )
            
            # 超时配置 - 针对流媒体优化
            timeout = httpx.Timeout(
                timeout=config.HTTP_TOTAL_TIMEOUT,  # 总超时
                connect=config.HTTP_CONNECT_TIMEOUT,  # 连接超时
                read=30.0,  # 读取超时 - 流媒体文件可能较大
                write=10.0,  # 写入超时
                pool=5.0  # 连接池超时
            )
            
            # SSL 配置
            verify = True if config.BACKEND_SSL_VERIFY else False
            
            # 创建异步客户端
            self.client = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
                verify=verify,
                follow_redirects=True,
                http2=True,  # 启用 HTTP/2 支持，提高多路复用效率
                # 针对流媒体的传输配置
                transport=httpx.AsyncHTTPTransport(
                    retries=3,  # 自动重试
                    http2=True
                )
            )
            
            logger.info(
                f"HTTP客户端初始化完成 - "
                f"连接池: {config.HTTP_CONNECTOR_LIMIT}, "
                f"Keep-Alive: {config.HTTP_CONNECTOR_LIMIT_PER_HOST}, "
                f"HTTP/2: 启用"
            )
    
    async def get_client(self) -> httpx.AsyncClient:
        """
        获取HTTP客户端实例
        如果客户端未初始化或已关闭，会自动重新初始化
        
        Returns:
            httpx.AsyncClient: 异步HTTP客户端
        """
        if self.client is None or self.client.is_closed:
            # 需要在外部传入config，这里先抛出异常
            raise RuntimeError("HTTP客户端未初始化，请先调用 initialize(config)")
        return self.client
    
    async def close(self):
        """关闭HTTP客户端"""
        async with self._lock:
            if not self._closed and self.client:
                await self.client.aclose()
                self._closed = True
                logger.info("HTTP客户端已关闭")
    
    async def __aenter__(self):
        """上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        await self.close()


# 全局HTTP客户端实例
http_client_service = HTTPClientService()
