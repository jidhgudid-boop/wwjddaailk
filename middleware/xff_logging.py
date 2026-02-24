"""
XFF (X-Forwarded-For) 日志中间件
修复 FastAPI/Uvicorn 访问日志不识别 X-Forwarded-For 头的问题

问题背景：
- Uvicorn 默认使用 request.client.host 作为客户端 IP 记录到访问日志
- 当服务运行在反向代理后时，request.client.host 显示的是代理服务器的 IP
- 真实客户端 IP 被保存在 X-Forwarded-For 或 X-Real-IP 头中

解决方案：
- 创建 ASGI 中间件，在请求进入时修改 scope['client'] 为真实客户端 IP
- 这样 Uvicorn 的访问日志会显示正确的客户端 IP
"""
import logging
from typing import Tuple, Optional
import ipaddress

from starlette.types import ASGIApp, Receive, Send, Scope


logger = logging.getLogger(__name__)


def get_real_client_ip_from_scope(scope: Scope) -> Optional[str]:
    """
    从 ASGI scope 中获取真实客户端 IP
    
    优先级：
    1. X-Forwarded-For 头（取第一个 IP）
    2. X-Real-IP 头
    3. 原始 scope['client']
    
    Args:
        scope: ASGI scope 字典
        
    Returns:
        规范化后的 IP 地址字符串，如果无法获取返回 None
    """
    headers = dict(scope.get("headers", []))
    
    # 优先使用 X-Forwarded-For
    xff = headers.get(b"x-forwarded-for")
    if xff:
        # X-Forwarded-For 格式: client, proxy1, proxy2, ...
        # 取第一个 IP（真实客户端）
        ip_str = xff.decode("utf-8", errors="ignore").split(",")[0].strip()
        return normalize_ip(ip_str)
    
    # 其次使用 X-Real-IP
    real_ip = headers.get(b"x-real-ip")
    if real_ip:
        ip_str = real_ip.decode("utf-8", errors="ignore").strip()
        return normalize_ip(ip_str)
    
    return None


def normalize_ip(ip_str: str) -> str:
    """
    规范化 IP 地址
    
    - IPv4: 保持原样
    - IPv6: 使用压缩格式
    - 无效 IP: 返回原字符串
    
    Args:
        ip_str: IP 地址字符串
        
    Returns:
        规范化后的 IP 地址
    """
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return str(ip_obj)
    except ValueError:
        return ip_str


class XFFLoggingMiddleware:
    """
    X-Forwarded-For 日志中间件
    
    修改 ASGI scope 中的 client 信息，使 Uvicorn 访问日志显示真实客户端 IP
    
    安全注意事项:
    - 当 trusted_proxies=None 时，中间件会无条件信任 X-Forwarded-For 头
    - 这适用于在可信网络环境中运行的服务，或者所有请求都来自可信代理的场景
    - 如果服务直接暴露在公网，强烈建议设置 trusted_proxies 参数
    - 设置 trusted_proxies 后，只有来自可信代理的请求才会处理 XFF 头
    
    使用方法：
        # 信任所有代理（仅在可信网络环境中使用）
        app.add_middleware(XFFLoggingMiddleware)
        
        # 配置可信代理（推荐用于生产环境）
        app.add_middleware(XFFLoggingMiddleware, trusted_proxies=["10.0.0.0/8", "192.168.0.0/16"])
    """
    
    def __init__(self, app: ASGIApp, trusted_proxies: Optional[list] = None):
        """
        初始化中间件
        
        Args:
            app: ASGI 应用
            trusted_proxies: 可信代理 IP 列表（可选，用于安全验证）
                             如果设置，只有来自这些 IP 的请求才会处理 XFF 头
                             支持单个 IP 和 CIDR 格式
                             如果不设置，将信任所有来源的 XFF 头（仅在可信网络环境中使用）
        """
        self.app = app
        self.trusted_proxies = trusted_proxies
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        ASGI 中间件入口
        
        Args:
            scope: ASGI scope
            receive: 接收函数
            send: 发送函数
        """
        if scope["type"] in ("http", "websocket"):
            # 获取真实客户端 IP
            real_ip = get_real_client_ip_from_scope(scope)
            
            if real_ip:
                # 验证可信代理（如果配置了）
                if self.trusted_proxies:
                    original_client = scope.get("client")
                    if original_client:
                        proxy_ip = original_client[0]
                        if not self._is_trusted_proxy(proxy_ip):
                            # 代理不可信，不修改 client
                            await self.app(scope, receive, send)
                            return
                
                # 修改 scope 中的 client 信息
                # client 是一个元组: (host, port)
                original_client = scope.get("client")
                original_port = original_client[1] if original_client else 0
                
                # 创建新的 scope 副本，避免修改原始 scope
                new_scope = scope.copy()
                new_scope["client"] = (real_ip, original_port)
                
                # 记录 IP 替换（仅在 DEBUG 级别）
                if logger.isEnabledFor(logging.DEBUG):
                    original_ip = original_client[0] if original_client else "unknown"
                    if original_ip != real_ip:
                        logger.debug(
                            f"XFF中间件: 客户端IP替换 {original_ip} -> {real_ip}"
                        )
                
                await self.app(new_scope, receive, send)
                return
        
        # 非 HTTP/WebSocket 请求或没有 XFF 头，直接传递
        await self.app(scope, receive, send)
    
    def _is_trusted_proxy(self, proxy_ip: str) -> bool:
        """
        检查代理 IP 是否可信
        
        Args:
            proxy_ip: 代理服务器 IP
            
        Returns:
            是否可信
        """
        if not self.trusted_proxies:
            return True
        
        try:
            proxy_addr = ipaddress.ip_address(proxy_ip)
            for trusted in self.trusted_proxies:
                try:
                    # 支持 CIDR 格式
                    if "/" in trusted:
                        network = ipaddress.ip_network(trusted, strict=False)
                        if proxy_addr in network:
                            return True
                    else:
                        if proxy_addr == ipaddress.ip_address(trusted):
                            return True
                except ValueError:
                    continue
        except ValueError:
            pass
        
        return False
