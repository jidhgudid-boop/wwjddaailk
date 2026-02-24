#!/usr/bin/env python3
"""
JS白名单追踪功能测试
Test JS Whitelist Tracker Feature
"""

import pytest
import requests
import json
import time

# 测试配置
BASE_URL = "http://localhost:7889"
API_KEY = "F2UkWEJZRBxC7"


class TestJSWhitelistTracker:
    """JS白名单追踪功能测试套件"""
    
    @pytest.fixture
    def test_uid(self):
        """测试用户ID"""
        return f"test_user_js_{int(time.time())}"
    
    @pytest.fixture
    def test_js_path(self):
        """测试JS文件路径"""
        return "static/js/test_app.js"
    
    def test_add_js_whitelist_success(self, test_uid, test_js_path):
        """测试添加JS白名单成功"""
        url = f"{BASE_URL}/api/js-whitelist"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "uid": test_uid,
            "jsPath": test_js_path
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "data" in result
        assert result["data"]["uid"] == test_uid
        assert result["data"]["js_path"] == test_js_path
        assert "client_ip" in result["data"]
        assert "ttl" in result["data"]
    
    def test_add_js_whitelist_missing_api_key(self, test_uid, test_js_path):
        """测试缺少API Key"""
        url = f"{BASE_URL}/api/js-whitelist"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "uid": test_uid,
            "jsPath": test_js_path
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        assert response.status_code == 403
        result = response.json()
        assert "error" in result
    
    def test_add_js_whitelist_invalid_api_key(self, test_uid, test_js_path):
        """测试无效的API Key"""
        url = f"{BASE_URL}/api/js-whitelist"
        headers = {
            "Authorization": "Bearer invalid_key",
            "Content-Type": "application/json"
        }
        data = {
            "uid": test_uid,
            "jsPath": test_js_path
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        assert response.status_code == 403
    
    def test_add_js_whitelist_missing_fields(self):
        """测试缺少必需字段"""
        url = f"{BASE_URL}/api/js-whitelist"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        # 缺少jsPath
        data = {"uid": "test_user"}
        response = requests.post(url, headers=headers, json=data)
        assert response.status_code == 400
        
        # 缺少uid
        data = {"jsPath": "test.js"}
        response = requests.post(url, headers=headers, json=data)
        assert response.status_code == 400
    
    def test_check_js_whitelist_after_adding(self, test_uid, test_js_path):
        """测试添加后检查白名单"""
        # 首先添加到白名单
        add_url = f"{BASE_URL}/api/js-whitelist"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "uid": test_uid,
            "jsPath": test_js_path
        }
        
        add_response = requests.post(add_url, headers=headers, json=data)
        assert add_response.status_code == 200
        
        # 然后检查白名单
        check_url = f"{BASE_URL}/api/js-whitelist/check"
        params = {
            "js_path": test_js_path,
            "uid": test_uid
        }
        
        check_response = requests.get(check_url, params=params)
        
        assert check_response.status_code == 200
        result = check_response.json()
        assert result["is_allowed"] is True
        assert result["js_path"] == test_js_path
        assert result["uid"] == test_uid
    
    def test_check_js_whitelist_not_in_whitelist(self):
        """测试检查不在白名单中的JS文件"""
        url = f"{BASE_URL}/api/js-whitelist/check"
        params = {
            "js_path": f"static/js/nonexistent_{int(time.time())}.js",
            "uid": "nonexistent_user"
        }
        
        response = requests.get(url, params=params)
        
        # 根据配置，可能返回200（功能未启用）或403（验证失败）
        assert response.status_code in [200, 403]
        result = response.json()
        
        if response.status_code == 403:
            assert result["is_allowed"] is False
    
    def test_get_js_whitelist_stats(self, test_uid, test_js_path):
        """测试获取白名单统计信息"""
        # 首先添加一些记录
        add_url = f"{BASE_URL}/api/js-whitelist"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        # 添加多个JS文件
        js_files = [
            f"{test_js_path}",
            f"static/js/test_utils_{int(time.time())}.js",
            f"static/js/test_main_{int(time.time())}.js"
        ]
        
        for js_file in js_files:
            data = {
                "uid": test_uid,
                "jsPath": js_file
            }
            requests.post(add_url, headers=headers, json=data)
        
        # 获取统计信息
        stats_url = f"{BASE_URL}/api/js-whitelist/stats"
        params = {"uid": test_uid}
        
        response = requests.get(stats_url, headers=headers, params=params)
        
        assert response.status_code == 200
        result = response.json()
        
        if result.get("enabled"):
            assert result["uid"] == test_uid
            assert result["total_entries"] >= len(js_files)
            assert "entries" in result
            assert "ttl_config" in result
    
    def test_get_js_whitelist_stats_missing_api_key(self, test_uid):
        """测试获取统计信息时缺少API Key"""
        url = f"{BASE_URL}/api/js-whitelist/stats"
        params = {"uid": test_uid}
        
        response = requests.get(url, params=params)
        
        assert response.status_code == 403
    
    def test_ua_and_ip_auto_extraction(self, test_uid, test_js_path):
        """测试UA和IP自动提取"""
        url = f"{BASE_URL}/api/js-whitelist"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "TestBot/1.0 (Auto UA IP Test)"
        }
        data = {
            "uid": test_uid,
            "jsPath": test_js_path
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        assert response.status_code == 200
        result = response.json()
        
        # 验证返回的数据包含自动提取的IP
        assert "client_ip" in result["data"]
        # IP应该不为空
        assert result["data"]["client_ip"]


class TestJSWhitelistIntegration:
    """JS白名单集成测试"""
    
    def test_full_workflow(self):
        """测试完整工作流程"""
        test_uid = f"integration_test_{int(time.time())}"
        test_js_path = f"static/js/integration_test_{int(time.time())}.js"
        
        # 步骤1: 添加到白名单
        add_url = f"{BASE_URL}/api/js-whitelist"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "uid": test_uid,
            "jsPath": test_js_path
        }
        
        add_response = requests.post(add_url, headers=headers, json=data)
        assert add_response.status_code == 200
        assert add_response.json()["success"] is True
        
        # 步骤2: 验证可以访问
        check_url = f"{BASE_URL}/api/js-whitelist/check"
        params = {
            "js_path": test_js_path,
            "uid": test_uid
        }
        
        check_response = requests.get(check_url, params=params)
        assert check_response.status_code == 200
        assert check_response.json()["is_allowed"] is True
        
        # 步骤3: 查看统计
        stats_url = f"{BASE_URL}/api/js-whitelist/stats"
        stats_params = {"uid": test_uid}
        
        stats_response = requests.get(stats_url, headers=headers, params=stats_params)
        assert stats_response.status_code == 200
        
        stats_result = stats_response.json()
        if stats_result.get("enabled"):
            assert stats_result["total_entries"] >= 1
        
        print(f"\n✅ 完整工作流程测试通过:")
        print(f"   - UID: {test_uid}")
        print(f"   - JS Path: {test_js_path}")
        print(f"   - 白名单记录数: {stats_result.get('total_entries', 'N/A')}")


def run_manual_tests():
    """运行手动测试"""
    print("\n" + "=" * 70)
    print("JS白名单追踪功能 - 手动测试")
    print("=" * 70)
    
    test_uid = f"manual_test_{int(time.time())}"
    test_js_path = "static/js/manual_test.js"
    
    print(f"\n测试配置:")
    print(f"  Base URL: {BASE_URL}")
    print(f"  API Key: {API_KEY[:10]}...")
    print(f"  Test UID: {test_uid}")
    print(f"  Test JS Path: {test_js_path}")
    
    # 测试1: 添加JS白名单
    print(f"\n[测试1] 添加JS白名单")
    try:
        url = f"{BASE_URL}/api/js-whitelist"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "uid": test_uid,
            "jsPath": test_js_path
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=5)
        print(f"  状态码: {response.status_code}")
        print(f"  响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print("  ✅ 测试通过")
        else:
            print("  ❌ 测试失败")
    except Exception as e:
        print(f"  ❌ 错误: {str(e)}")
    
    # 测试2: 检查白名单
    print(f"\n[测试2] 检查白名单")
    try:
        url = f"{BASE_URL}/api/js-whitelist/check"
        params = {
            "js_path": test_js_path,
            "uid": test_uid
        }
        
        response = requests.get(url, params=params, timeout=5)
        print(f"  状态码: {response.status_code}")
        print(f"  响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print("  ✅ 测试通过")
        else:
            print("  ❌ 测试失败")
    except Exception as e:
        print(f"  ❌ 错误: {str(e)}")
    
    # 测试3: 获取统计
    print(f"\n[测试3] 获取统计信息")
    try:
        url = f"{BASE_URL}/api/js-whitelist/stats"
        headers = {
            "Authorization": f"Bearer {API_KEY}"
        }
        params = {"uid": test_uid}
        
        response = requests.get(url, headers=headers, params=params, timeout=5)
        print(f"  状态码: {response.status_code}")
        print(f"  响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print("  ✅ 测试通过")
        else:
            print("  ❌ 测试失败")
    except Exception as e:
        print(f"  ❌ 错误: {str(e)}")
    
    print("\n" + "=" * 70)
    print("手动测试完成")
    print("=" * 70)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "manual":
        run_manual_tests()
    else:
        print("运行pytest测试套件...")
        print("提示: 使用 'python test_js_whitelist.py manual' 运行手动测试")
        pytest.main([__file__, "-v", "-s"])
