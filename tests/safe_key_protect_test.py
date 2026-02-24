#!/usr/bin/env python3
"""
Safe Key Protect 功能测试脚本
测试安全密钥保护重定向功能
"""

import sys
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio
from aiohttp import web
import json

# 导入主应用模块
sys.path.append('.')
from app import proxy_handler, OptimizedConfig, extract_match_key, cors_headers

class TestSafeKeyProtect(unittest.TestCase):
    """Safe Key Protect 功能测试"""
    
    def setUp(self):
        """测试设置"""
        self.original_config = OptimizedConfig()
        # 保存原始配置
        self.original_safe_key_protect = getattr(OptimizedConfig, 'SAFE_KEY_PROTECT_ENABLED', False)
        self.original_redirect_url = getattr(OptimizedConfig, 'SAFE_KEY_PROTECT_REDIRECT_BASE_URL', '')
    
    def tearDown(self):
        """测试清理"""
        OptimizedConfig.SAFE_KEY_PROTECT_ENABLED = self.original_safe_key_protect
        OptimizedConfig.SAFE_KEY_PROTECT_REDIRECT_BASE_URL = self.original_redirect_url
    
    def test_extract_match_key(self):
        """测试密钥提取功能"""
        test_cases = [
            ("wp-content/uploads/video/2025-08-30/4ad2ee3021_22U6pQ/720p_2e2809/index.m3u8", "4ad2ee3021_22U6pQ"),
            ("wp-content/uploads/video/2025-08-28/811b04aa16_rcg1dy/720p_bec466/index.m3u8", "811b04aa16_rcg1dy"),
            ("wp-content/uploads/video/2025-08-28/4c58e7d7cb_KYHFAI/720p_68d91d/index.m3u8", "4c58e7d7cb_KYHFAI"),
            ("some/random/path/without/key", None),
            ("", None)
        ]
        
        for path, expected_key in test_cases:
            with self.subTest(path=path):
                result = extract_match_key(path)
                self.assertEqual(result, expected_key, f"路径 '{path}' 应该提取出密钥 '{expected_key}'，但得到 '{result}'")
    
    @patch('app.redis_manager')
    @patch('app.check_ip_key_path')
    async def test_safe_key_protect_disabled(self, mock_check_ip, mock_redis):
        """测试Safe Key Protect禁用时的行为"""
        # 设置配置 - 禁用Safe Key Protect
        OptimizedConfig.SAFE_KEY_PROTECT_ENABLED = False
        
        # 模拟IP检查失败
        mock_check_ip.return_value = (False, None)
        
        # 创建模拟请求
        request = MagicMock()
        request.method = "GET"
        request.query = {}
        request.match_info = {"path": "wp-content/uploads/video/2025-08-30/4ad2ee3021_22U6pQ/720p_2e2809/index.m3u8"}
        request.url = "http://test.com/wp-content/uploads/video/2025-08-30/4ad2ee3021_22U6pQ/720p_2e2809/index.m3u8"
        request.headers = {"User-Agent": "TestAgent"}
        request.cookies = {}
        
        # 模拟获取客户端IP
        with patch('app.get_client_ip', return_value='192.168.1.1'):
            response = await proxy_handler(request)
        
        # 验证返回403状态码（不是重定向）
        self.assertEqual(response.status, 403)
        self.assertIn("Access Denied", response.text)
    
    @patch('app.redis_manager')
    @patch('app.check_ip_key_path')
    async def test_safe_key_protect_enabled_with_key(self, mock_check_ip, mock_redis):
        """测试Safe Key Protect启用且有密钥时的重定向行为"""
        # 设置配置 - 启用Safe Key Protect
        OptimizedConfig.SAFE_KEY_PROTECT_ENABLED = True
        OptimizedConfig.SAFE_KEY_PROTECT_REDIRECT_BASE_URL = "https://v.yuelk.com/pyvideo2/keyroute/"
        
        # 模拟IP检查失败
        mock_check_ip.return_value = (False, None)
        
        # 创建模拟请求
        test_path = "wp-content/uploads/video/2025-08-30/4ad2ee3021_22U6pQ/720p_2e2809/index.m3u8"
        request = MagicMock()
        request.method = "GET"
        request.query = {}
        request.match_info = {"path": test_path}
        request.url = f"http://test.com/{test_path}"
        request.headers = {"User-Agent": "TestAgent"}
        request.cookies = {}
        
        # 模拟获取客户端IP
        with patch('app.get_client_ip', return_value='192.168.1.1'):
            response = await proxy_handler(request)
        
        # 验证返回302重定向状态码
        self.assertEqual(response.status, 302)
        expected_redirect_url = f"https://v.yuelk.com/pyvideo2/keyroute/{test_path}"
        self.assertEqual(response.headers['Location'], expected_redirect_url)
        print(f"✅ 重定向测试通过: {expected_redirect_url}")
    
    @patch('app.redis_manager')
    @patch('app.check_ip_key_path')
    async def test_safe_key_protect_enabled_without_key(self, mock_check_ip, mock_redis):
        """测试Safe Key Protect启用但没有密钥时的行为"""
        # 设置配置 - 启用Safe Key Protect
        OptimizedConfig.SAFE_KEY_PROTECT_ENABLED = True
        OptimizedConfig.SAFE_KEY_PROTECT_REDIRECT_BASE_URL = "https://v.yuelk.com/pyvideo2/keyroute/"
        
        # 模拟IP检查失败
        mock_check_ip.return_value = (False, None)
        
        # 创建模拟请求（没有密钥的路径）
        test_path = "some/random/static/file.js"
        request = MagicMock()
        request.method = "GET"
        request.query = {}
        request.match_info = {"path": test_path}
        request.url = f"http://test.com/{test_path}"
        request.headers = {"User-Agent": "TestAgent"}
        request.cookies = {}
        
        # 模拟获取客户端IP
        with patch('app.get_client_ip', return_value='192.168.1.1'):
            response = await proxy_handler(request)
        
        # 验证返回403状态码（不是重定向，因为没有密钥）
        self.assertEqual(response.status, 403)
        self.assertIn("Access Denied", response.text)
        print("✅ 非密钥路径测试通过: 正确返回403而不是重定向")
    
    def test_configuration_exists(self):
        """测试配置项是否正确添加"""
        # 验证配置项存在
        self.assertTrue(hasattr(OptimizedConfig, 'SAFE_KEY_PROTECT_ENABLED'))
        self.assertTrue(hasattr(OptimizedConfig, 'SAFE_KEY_PROTECT_REDIRECT_BASE_URL'))
        
        # 验证默认值
        self.assertFalse(OptimizedConfig.SAFE_KEY_PROTECT_ENABLED)
        self.assertEqual(OptimizedConfig.SAFE_KEY_PROTECT_REDIRECT_BASE_URL, 
                        "https://v.yuelk.com/pyvideo2/keyroute/")
        print("✅ 配置项测试通过")

async def run_async_tests():
    """运行异步测试"""
    suite = unittest.TestSuite()
    test_instance = TestSafeKeyProtect()
    
    # 添加异步测试
    await test_instance.test_safe_key_protect_disabled()
    print("✅ 禁用状态测试完成")
    
    await test_instance.test_safe_key_protect_enabled_with_key()
    print("✅ 启用状态重定向测试完成")
    
    await test_instance.test_safe_key_protect_enabled_without_key()
    print("✅ 非密钥路径测试完成")

def main():
    """主测试函数"""
    print("=== Safe Key Protect 功能测试 ===\n")
    
    # 运行同步测试
    test_instance = TestSafeKeyProtect()
    test_instance.setUp()
    
    try:
        # 测试密钥提取
        test_instance.test_extract_match_key()
        print("✅ 密钥提取测试通过")
        
        # 测试配置
        test_instance.test_configuration_exists()
        
        # 运行异步测试
        print("\n--- 异步测试 ---")
        asyncio.run(run_async_tests())
        
        print("\n🎉 所有测试通过！Safe Key Protect功能正常工作。")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False
    finally:
        test_instance.tearDown()
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)