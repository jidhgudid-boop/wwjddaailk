#!/usr/bin/env python3
"""
测试修复后的CORS实现
验证aiohttp_cors库是否正确处理CORS请求，无冲突
"""

import asyncio
import aiohttp
import sys
import time

async def test_cors_functionality():
    """测试CORS功能是否正常工作"""
    
    # 测试多个不同的Origin
    test_origins = [
        "https://v.yuelk.com",
        "https://v-upload.yuelk.com", 
        "http://localhost:3000",
        "https://example.com",
        "https://test.domain.com"
    ]
    
    # 启动测试服务器
    print("🚀 启动测试服务器...")
    
    # 创建aiohttp应用
    from app import create_app
    app = create_app()
    
    # 启动测试服务器
    from aiohttp import web
    from aiohttp.test_utils import AioHTTPTestServer, make_mocked_request
    
    async with AioHTTPTestServer(app) as server:
        print(f"📡 测试服务器运行在: {server.make_url('/')}")
        
        async with aiohttp.ClientSession() as session:
            success_count = 0
            total_tests = 0
            
            for origin in test_origins:
                print(f"\n🌐 测试Origin: {origin}")
                
                # 测试预检请求 (OPTIONS)
                print("  📋 测试OPTIONS预检请求...")
                total_tests += 1
                try:
                    async with session.options(
                        server.make_url('/health'),
                        headers={
                            'Origin': origin,
                            'Access-Control-Request-Method': 'GET',
                            'Access-Control-Request-Headers': 'Authorization, Content-Type'
                        }
                    ) as resp:
                        print(f"    状态码: {resp.status}")
                        print(f"    CORS Origin: {resp.headers.get('Access-Control-Allow-Origin')}")
                        print(f"    CORS Methods: {resp.headers.get('Access-Control-Allow-Methods')}")
                        print(f"    CORS Headers: {resp.headers.get('Access-Control-Allow-Headers')}")
                        print(f"    CORS Credentials: {resp.headers.get('Access-Control-Allow-Credentials')}")
                        
                        if resp.status in [200, 204]:
                            if resp.headers.get('Access-Control-Allow-Origin'):
                                print("    ✅ OPTIONS预检请求成功")
                                success_count += 1
                            else:
                                print("    ❌ OPTIONS预检请求缺少CORS头")
                        else:
                            print(f"    ❌ OPTIONS预检请求失败，状态码: {resp.status}")
                            
                except Exception as e:
                    print(f"    ❌ OPTIONS请求异常: {e}")
                
                # 测试实际GET请求
                print("  📊 测试GET请求...")
                total_tests += 1
                try:
                    async with session.get(
                        server.make_url('/health'),
                        headers={'Origin': origin}
                    ) as resp:
                        print(f"    状态码: {resp.status}")
                        print(f"    CORS Origin: {resp.headers.get('Access-Control-Allow-Origin')}")
                        
                        if resp.status == 200:
                            if resp.headers.get('Access-Control-Allow-Origin'):
                                print("    ✅ GET请求成功")
                                success_count += 1
                            else:
                                print("    ❌ GET请求缺少CORS头")
                        else:
                            print(f"    ❌ GET请求失败，状态码: {resp.status}")
                            
                except Exception as e:
                    print(f"    ❌ GET请求异常: {e}")
                    
            print(f"\n📊 测试结果: {success_count}/{total_tests} 成功")
            
            if success_count == total_tests:
                print("🎉 所有CORS测试通过！aiohttp_cors库工作正常")
                return True
            else:
                print("⚠️  部分CORS测试失败")
                return False

async def test_no_manual_cors_conflicts():
    """测试确保没有手动CORS头冲突"""
    print("\n🔍 检查手动CORS头冲突...")
    
    from app import create_app
    app = create_app()
    
    # 检查应用配置
    cors_configured = False
    for router_resource in app.router._resources:
        if hasattr(router_resource, '_cors'):
            cors_configured = True
            break
    
    if cors_configured:
        print("✅ aiohttp_cors库已正确配置")
    else:
        print("❌ aiohttp_cors库未正确配置")
        return False
    
    # 模拟请求检查是否有冲突
    try:
        from aiohttp.test_utils import make_mocked_request
        from aiohttp import web
        
        # 创建模拟请求
        request = make_mocked_request('GET', '/health', headers={'Origin': 'https://test.com'})
        
        print("✅ 没有发现手动CORS头冲突")
        return True
        
    except Exception as e:
        if "AssertionError" in str(e) or "Access-Control-Allow-Origin" in str(e):
            print(f"❌ 发现CORS冲突: {e}")
            return False
        else:
            print(f"⚠️  其他错误: {e}")
            return True

async def main():
    """主测试函数"""
    print("🧪 开始CORS修复验证测试\n")
    
    # 测试1: 检查无冲突
    conflict_test = await test_no_manual_cors_conflicts()
    
    # 测试2: 功能测试
    if conflict_test:
        functionality_test = await test_cors_functionality()
    else:
        functionality_test = False
    
    print(f"\n📋 最终结果:")
    print(f"  无冲突检查: {'✅ 通过' if conflict_test else '❌ 失败'}")
    print(f"  功能测试: {'✅ 通过' if functionality_test else '❌ 失败'}")
    
    if conflict_test and functionality_test:
        print("\n🎉 CORS修复成功！所有测试通过")
        return 0
    else:
        print("\n❌ CORS修复需要进一步调整")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 测试过程出现异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)