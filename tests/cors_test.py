#!/usr/bin/env python3
"""
CORS 功能测试脚本
测试新的CORS优化是否正确工作
"""

import sys
import asyncio
import aiohttp
import json
from unittest.mock import Mock

# Add the current directory to Python path
sys.path.insert(0, '/home/runner/work/YuemPyScripts/YuemPyScripts/Server/文件代理')

try:
    from app import cors_headers, create_app
    print("✓ Successfully imported cors_headers and create_app from app.py")
except ImportError as e:
    print(f"✗ Failed to import from app.py: {e}")
    sys.exit(1)

def test_cors_headers_function():
    """测试 cors_headers 函数的基本功能"""
    print("\n=== 测试 cors_headers 函数 ===")
    
    # 测试1：无请求对象（向后兼容）
    print("1. 测试无请求对象的情况...")
    headers = cors_headers()
    print(f"   返回的头: {headers}")
    
    # 验证基本头部存在
    required_headers = [
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Methods", 
        "Access-Control-Allow-Headers",
        "Access-Control-Allow-Credentials",
        "Access-Control-Max-Age",
        "Vary"
    ]
    
    for header in required_headers:
        if header in headers:
            print(f"   ✓ {header}: {headers[header]}")
        else:
            print(f"   ✗ 缺失头部: {header}")
            return False
    
    # 测试2：有请求对象但无Origin头
    print("\n2. 测试有请求对象但无Origin头...")
    mock_request = Mock()
    mock_request.headers = {}
    
    headers = cors_headers(mock_request)
    print(f"   Access-Control-Allow-Origin: {headers['Access-Control-Allow-Origin']}")
    
    # 测试3：有请求对象且有Origin头
    print("\n3. 测试有请求对象且有Origin头...")
    mock_request_with_origin = Mock()
    mock_request_with_origin.headers = {'Origin': 'https://example.com'}
    
    headers = cors_headers(mock_request_with_origin)
    expected_origin = 'https://example.com'
    actual_origin = headers['Access-Control-Allow-Origin']
    
    print(f"   请求的Origin: {expected_origin}")
    print(f"   返回的Access-Control-Allow-Origin: {actual_origin}")
    
    if actual_origin == expected_origin:
        print("   ✓ Origin正确映射!")
    else:
        print("   ✗ Origin映射失败!")
        return False
    
    # 测试4：测试多个不同的Origin
    print("\n4. 测试多个不同的Origin...")
    test_origins = [
        'https://v.yuelk.com',
        'https://v-upload.yuelk.com', 
        'https://example.com',
        'http://localhost:3000',
        'https://subdomain.example.org'
    ]
    
    for origin in test_origins:
        mock_req = Mock()
        mock_req.headers = {'Origin': origin}
        headers = cors_headers(mock_req)
        actual = headers['Access-Control-Allow-Origin']
        
        if actual == origin:
            print(f"   ✓ {origin} -> {actual}")
        else:
            print(f"   ✗ {origin} -> {actual} (不匹配)")
            return False
    
    print("\n✅ cors_headers 函数测试通过!")
    return True

def test_cors_headers_security():
    """测试CORS头部的安全性"""
    print("\n=== 测试CORS安全性 ===")
    
    # 测试credentials和origin的组合
    mock_request = Mock()
    mock_request.headers = {'Origin': 'https://malicious.com'}
    
    headers = cors_headers(mock_request)
    
    # 检查是否允许credentials
    if headers.get('Access-Control-Allow-Credentials') == 'true':
        origin = headers.get('Access-Control-Allow-Origin')
        if origin == '*':
            print("   ✗ 安全风险: credentials=true 时不应该使用 Origin=*")
            return False
        else:
            print(f"   ✓ 安全检查通过: credentials=true, Origin={origin}")
    
    # 检查Vary头是否存在
    if 'Vary' in headers:
        print(f"   ✓ Vary头存在: {headers['Vary']}")
    else:
        print("   ✗ 缺失Vary头，可能导致缓存问题")
        return False
    
    print("✅ CORS安全性测试通过!")
    return True

async def test_app_integration():
    """测试应用集成中的CORS"""
    print("\n=== 测试应用集成 ===")
    
    try:
        # 简化版本 - 创建应用实例并测试基本功能
        app = create_app()
        print("   ✓ 应用创建成功")
        
        # 这里我们简化测试，仅验证应用可以创建和配置正确
        # 实际的HTTP请求测试需要更复杂的设置
        
        # 测试路由是否正确配置
        routes = []
        for resource in app.router.resources():
            for route in resource:
                routes.append(f"{route.method} {route.resource.canonical}")
        
        print(f"   ✓ 发现 {len(routes)} 个路由")
        
        # 检查关键路由是否存在
        key_routes = ['/health', '/api/whitelist', '/debug/browser']
        for key_route in key_routes:
            found = any(key_route in route for route in routes)
            if found:
                print(f"   ✓ 关键路由存在: {key_route}")
            else:
                print(f"   ✗ 关键路由缺失: {key_route}")
                return False
        
        print("✅ 应用集成测试通过!")
        return True
        
    except Exception as e:
        print(f"   ✗ 应用集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cors_coverage():
    """检查所有API端点的CORS覆盖"""
    print("\n=== 检查CORS覆盖范围 ===")
    
    # 这里我们检查代码中是否所有的响应都使用了 cors_headers(request)
    with open('/home/runner/work/YuemPyScripts/YuemPyScripts/Server/文件代理/app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找可能遗漏的 cors_headers() 调用（不带request参数）
    lines = content.split('\n')
    problematic_lines = []
    
    for i, line in enumerate(lines, 1):
        if 'cors_headers()' in line and 'def cors_headers' not in line:
            problematic_lines.append((i, line.strip()))
    
    if problematic_lines:
        print(f"   ✗ 发现 {len(problematic_lines)} 处可能遗漏request参数的cors_headers()调用:")
        for line_num, line in problematic_lines:
            print(f"     第{line_num}行: {line}")
        return False
    else:
        print("   ✓ 所有cors_headers调用都已更新为使用request参数")
    
    print("✅ CORS覆盖范围检查通过!")
    return True

def main():
    """主测试函数"""
    print("🚀 CORS 功能优化测试")
    print("=" * 60)
    print("测试目标: 确保允许任何CORS来源")
    print("=" * 60)
    
    tests = [
        ("CORS函数基础功能", test_cors_headers_function),
        ("CORS安全性检查", test_cors_headers_security), 
        ("CORS覆盖范围检查", test_cors_coverage),
    ]
    
    passed = 0
    total = len(tests)
    
    try:
        for test_name, test_func in tests:
            print(f"\n📋 执行测试: {test_name}")
            print("-" * 40)
            
            if test_func():
                passed += 1
                print(f"✅ {test_name} - 通过")
            else:
                print(f"❌ {test_name} - 失败")
        
        # 运行异步测试
        print(f"\n📋 执行测试: 应用集成测试")
        print("-" * 40)
        
        if asyncio.run(test_app_integration()):
            passed += 1
            total += 1
            print(f"✅ 应用集成测试 - 通过")
        else:
            total += 1
            print(f"❌ 应用集成测试 - 失败")
        
        print("\n" + "=" * 60)
        print(f"📊 测试结果: {passed}/{total} 测试通过")
        
        if passed == total:
            print("🎉 所有测试通过!")
            print("\n✅ CORS优化验证结果:")
            print("✅ 现在支持任何来源的CORS请求")
            print("✅ 保持安全性(credentials + 动态origin)")
            print("✅ 向后兼容性良好")
            print("✅ 所有API端点都已更新")
            print("\n📝 实现详情:")
            print("   - 使用动态Origin头映射")
            print("   - 保持Access-Control-Allow-Credentials: true")
            print("   - 添加Vary: Origin头以确保正确缓存")
            print("   - 所有API端点统一更新")
            return True
        else:
            print("❌ 部分测试失败!")
            print("❌ CORS优化可能存在问题")
            return False
            
    except Exception as e:
        print(f"\n❌ 测试执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)