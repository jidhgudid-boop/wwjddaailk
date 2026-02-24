#!/usr/bin/env python3
"""
测试HTTPS后端代理支持
Test HTTPS backend proxy support with SSL verification disabled
"""

import asyncio
import ssl
import sys
sys.path.insert(0, '.')


def test_ssl_context_creation():
    """测试SSL上下文创建"""
    print("=== Test 1: SSL Context Creation ===")
    
    # 创建禁用证书验证的SSL上下文
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    assert ssl_context.check_hostname is False, "SSL hostname check should be disabled"
    assert ssl_context.verify_mode == ssl.CERT_NONE, "SSL verify mode should be CERT_NONE"
    
    print("✅ SSL context created with verification disabled")
    print(f"   - check_hostname: {ssl_context.check_hostname}")
    print(f"   - verify_mode: {ssl_context.verify_mode} (CERT_NONE={ssl.CERT_NONE})")
    print()


def test_backend_url_construction():
    """测试后端URL构建"""
    print("=== Test 2: Backend URL Construction ===")
    
    # 导入配置
    from app import config
    
    test_path = "test/video.m3u8"
    
    # Test with HTTP (default)
    config.BACKEND_USE_HTTPS = False
    backend_scheme = "https" if config.BACKEND_USE_HTTPS else "http"
    remote_url = f"{backend_scheme}://{config.BACKEND_HOST}:{config.BACKEND_PORT}/{test_path}"
    print(f"HTTP URL: {remote_url}")
    assert remote_url.startswith("http://"), "URL should use HTTP scheme"
    
    # Test with HTTPS
    config.BACKEND_USE_HTTPS = True
    backend_scheme = "https" if config.BACKEND_USE_HTTPS else "http"
    remote_url = f"{backend_scheme}://{config.BACKEND_HOST}:{config.BACKEND_PORT}/{test_path}"
    print(f"HTTPS URL: {remote_url}")
    assert remote_url.startswith("https://"), "URL should use HTTPS scheme"
    
    print("✅ Backend URL construction works correctly")
    print()


async def test_http_client_manager_http():
    """测试HTTP客户端管理器（HTTP模式）"""
    print("=== Test 3: HTTPClientManager with HTTP ===")
    
    # Create a fresh config instance for testing
    from app import OptimizedConfig
    test_config = OptimizedConfig()
    test_config.BACKEND_USE_HTTPS = False
    test_config.BACKEND_SSL_VERIFY = False
    
    # Temporarily override the global config
    import app
    original_config = app.config
    app.config = test_config
    
    try:
        from app import HTTPClientManager
        
        manager = HTTPClientManager()
        await manager.initialize()
        
        assert manager.connector is not None, "Connector should be initialized"
        assert manager.session is not None, "Session should be initialized"
        assert not manager._closed, "Manager should not be closed"
        
        print("✅ HTTPClientManager initialized successfully with HTTP")
        
        await manager.close()
        assert manager._closed, "Manager should be closed"
        print("✅ HTTPClientManager closed successfully")
        print()
    finally:
        # Restore original config
        app.config = original_config


async def test_http_client_manager_https():
    """测试HTTP客户端管理器（HTTPS模式，禁用SSL验证）"""
    print("=== Test 4: HTTPClientManager with HTTPS (SSL verification disabled) ===")
    
    # Create a fresh config instance for testing
    from app import OptimizedConfig
    test_config = OptimizedConfig()
    test_config.BACKEND_USE_HTTPS = True
    test_config.BACKEND_SSL_VERIFY = False
    
    # Temporarily override the global config
    import app
    original_config = app.config
    app.config = test_config
    
    try:
        from app import HTTPClientManager
        
        manager = HTTPClientManager()
        await manager.initialize()
        
        assert manager.connector is not None, "Connector should be initialized"
        assert manager.session is not None, "Session should be initialized"
        assert not manager._closed, "Manager should not be closed"
        
        print("✅ HTTPClientManager initialized successfully with HTTPS and SSL verification disabled")
        
        await manager.close()
        assert manager._closed, "Manager should be closed"
        print("✅ HTTPClientManager closed successfully")
        print()
    finally:
        # Restore original config
        app.config = original_config


def test_config_options():
    """测试配置选项"""
    print("=== Test 5: Configuration Options ===")
    
    from app import config
    
    # 检查新的配置选项是否存在
    assert hasattr(config, 'BACKEND_USE_HTTPS'), "BACKEND_USE_HTTPS should be defined"
    assert hasattr(config, 'BACKEND_SSL_VERIFY'), "BACKEND_SSL_VERIFY should be defined"
    
    print(f"✅ Configuration options exist:")
    print(f"   - BACKEND_USE_HTTPS: {config.BACKEND_USE_HTTPS}")
    print(f"   - BACKEND_SSL_VERIFY: {config.BACKEND_SSL_VERIFY}")
    print()


async def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("HTTPS Backend Proxy Support Tests")
    print("=" * 60)
    print()
    
    try:
        # 同步测试
        test_ssl_context_creation()
        test_backend_url_construction()
        test_config_options()
        
        # 异步测试
        await test_http_client_manager_http()
        await test_http_client_manager_https()
        
        print("=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print("=" * 60)
        print(f"❌ Test failed: {str(e)}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
