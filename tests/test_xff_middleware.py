#!/usr/bin/env python3
"""
XFF (X-Forwarded-For) 日志中间件测试
Test XFF Logging Middleware
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestXFFLoggingMiddleware:
    """XFF 日志中间件测试套件"""
    
    @pytest.fixture
    def mock_app(self):
        """创建模拟的 ASGI 应用"""
        return AsyncMock()
    
    def test_get_real_client_ip_from_xff_header(self):
        """测试从 X-Forwarded-For 头获取真实客户端 IP"""
        from middleware.xff_logging import get_real_client_ip_from_scope
        
        scope = {
            "type": "http",
            "headers": [
                (b"x-forwarded-for", b"203.0.113.50, 70.41.3.18, 150.172.238.178"),
            ],
            "client": ("127.0.0.1", 12345)
        }
        
        ip = get_real_client_ip_from_scope(scope)
        assert ip == "203.0.113.50"
    
    def test_get_real_client_ip_from_x_real_ip_header(self):
        """测试从 X-Real-IP 头获取真实客户端 IP"""
        from middleware.xff_logging import get_real_client_ip_from_scope
        
        scope = {
            "type": "http",
            "headers": [
                (b"x-real-ip", b"203.0.113.50"),
            ],
            "client": ("127.0.0.1", 12345)
        }
        
        ip = get_real_client_ip_from_scope(scope)
        assert ip == "203.0.113.50"
    
    def test_get_real_client_ip_xff_priority_over_x_real_ip(self):
        """测试 X-Forwarded-For 优先于 X-Real-IP"""
        from middleware.xff_logging import get_real_client_ip_from_scope
        
        scope = {
            "type": "http",
            "headers": [
                (b"x-forwarded-for", b"203.0.113.50"),
                (b"x-real-ip", b"192.168.1.1"),
            ],
            "client": ("127.0.0.1", 12345)
        }
        
        ip = get_real_client_ip_from_scope(scope)
        assert ip == "203.0.113.50"
    
    def test_get_real_client_ip_no_headers(self):
        """测试没有相关头时返回 None"""
        from middleware.xff_logging import get_real_client_ip_from_scope
        
        scope = {
            "type": "http",
            "headers": [
                (b"content-type", b"application/json"),
            ],
            "client": ("127.0.0.1", 12345)
        }
        
        ip = get_real_client_ip_from_scope(scope)
        assert ip is None
    
    def test_get_real_client_ip_ipv6(self):
        """测试 IPv6 地址处理"""
        from middleware.xff_logging import get_real_client_ip_from_scope
        
        scope = {
            "type": "http",
            "headers": [
                (b"x-forwarded-for", b"2001:db8::1"),
            ],
            "client": ("::1", 12345)
        }
        
        ip = get_real_client_ip_from_scope(scope)
        assert ip == "2001:db8::1"
    
    def test_normalize_ip_ipv4(self):
        """测试 IPv4 地址规范化"""
        from middleware.xff_logging import normalize_ip
        
        assert normalize_ip("192.168.1.1") == "192.168.1.1"
        assert normalize_ip("10.0.0.1") == "10.0.0.1"
    
    def test_normalize_ip_ipv6(self):
        """测试 IPv6 地址规范化"""
        from middleware.xff_logging import normalize_ip
        
        # 完整格式应转换为压缩格式
        assert normalize_ip("2001:0db8:0000:0000:0000:0000:0000:0001") == "2001:db8::1"
        assert normalize_ip("2001:db8::1") == "2001:db8::1"
    
    def test_normalize_ip_invalid(self):
        """测试无效 IP 地址处理"""
        from middleware.xff_logging import normalize_ip
        
        # 无效 IP 应返回原字符串
        assert normalize_ip("invalid_ip") == "invalid_ip"
        assert normalize_ip("") == ""
    
    @pytest.mark.asyncio
    async def test_middleware_modifies_scope(self, mock_app):
        """测试中间件修改 scope 中的 client"""
        from middleware.xff_logging import XFFLoggingMiddleware
        
        middleware = XFFLoggingMiddleware(mock_app)
        
        original_scope = {
            "type": "http",
            "headers": [
                (b"x-forwarded-for", b"203.0.113.50"),
            ],
            "client": ("127.0.0.1", 12345)
        }
        
        captured_scope = None
        
        async def capture_app(scope, receive, send):
            nonlocal captured_scope
            captured_scope = scope
        
        middleware.app = capture_app
        
        await middleware(original_scope, AsyncMock(), AsyncMock())
        
        # 验证 scope 中的 client 被修改
        assert captured_scope is not None
        assert captured_scope["client"] == ("203.0.113.50", 12345)
    
    @pytest.mark.asyncio
    async def test_middleware_no_xff_header(self, mock_app):
        """测试没有 XFF 头时不修改 scope"""
        from middleware.xff_logging import XFFLoggingMiddleware
        
        middleware = XFFLoggingMiddleware(mock_app)
        
        original_scope = {
            "type": "http",
            "headers": [
                (b"content-type", b"application/json"),
            ],
            "client": ("127.0.0.1", 12345)
        }
        
        captured_scope = None
        
        async def capture_app(scope, receive, send):
            nonlocal captured_scope
            captured_scope = scope
        
        middleware.app = capture_app
        
        await middleware(original_scope, AsyncMock(), AsyncMock())
        
        # 验证使用原始 scope（client 未被修改）
        assert captured_scope is not None
        assert captured_scope["client"] == ("127.0.0.1", 12345)
    
    @pytest.mark.asyncio
    async def test_middleware_non_http_request(self, mock_app):
        """测试非 HTTP 请求直接传递"""
        from middleware.xff_logging import XFFLoggingMiddleware
        
        middleware = XFFLoggingMiddleware(mock_app)
        
        original_scope = {
            "type": "lifespan",  # 非 HTTP 类型
        }
        
        await middleware(original_scope, AsyncMock(), AsyncMock())
        
        # 验证直接调用原始应用
        mock_app.assert_called_once()
    
    def test_is_trusted_proxy_single_ip(self):
        """测试单个 IP 可信代理检查"""
        from middleware.xff_logging import XFFLoggingMiddleware
        
        middleware = XFFLoggingMiddleware(
            AsyncMock(),
            trusted_proxies=["10.0.0.1", "192.168.1.1"]
        )
        
        assert middleware._is_trusted_proxy("10.0.0.1") is True
        assert middleware._is_trusted_proxy("192.168.1.1") is True
        assert middleware._is_trusted_proxy("192.168.1.2") is False
    
    def test_is_trusted_proxy_cidr(self):
        """测试 CIDR 可信代理检查"""
        from middleware.xff_logging import XFFLoggingMiddleware
        
        middleware = XFFLoggingMiddleware(
            AsyncMock(),
            trusted_proxies=["10.0.0.0/24", "192.168.0.0/16"]
        )
        
        assert middleware._is_trusted_proxy("10.0.0.1") is True
        assert middleware._is_trusted_proxy("10.0.0.254") is True
        assert middleware._is_trusted_proxy("10.0.1.1") is False
        assert middleware._is_trusted_proxy("192.168.100.1") is True


class TestXFFMiddlewareIntegration:
    """XFF 中间件集成测试"""
    
    def test_xff_header_parsing_with_spaces(self):
        """测试 X-Forwarded-For 头带空格的解析"""
        from middleware.xff_logging import get_real_client_ip_from_scope
        
        scope = {
            "type": "http",
            "headers": [
                (b"x-forwarded-for", b" 203.0.113.50 , 70.41.3.18 , 150.172.238.178 "),
            ],
        }
        
        ip = get_real_client_ip_from_scope(scope)
        assert ip == "203.0.113.50"
    
    def test_xff_header_single_ip(self):
        """测试单个 IP 的 X-Forwarded-For 头"""
        from middleware.xff_logging import get_real_client_ip_from_scope
        
        scope = {
            "type": "http",
            "headers": [
                (b"x-forwarded-for", b"203.0.113.50"),
            ],
        }
        
        ip = get_real_client_ip_from_scope(scope)
        assert ip == "203.0.113.50"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
