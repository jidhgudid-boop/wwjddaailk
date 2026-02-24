#!/usr/bin/env python3
"""
简单的CORS测试，直接测试应用启动和CORS响应
"""

import asyncio
import aiohttp
import sys
import time

async def test_app_startup():
    """测试应用启动和基本CORS功能"""
    print("🚀 测试应用启动...")
    
    try:
        from app import create_app
        app = create_app()
        print("✅ 应用创建成功")
        
        # 启动测试服务器
        from aiohttp import web
        from aiohttp.test_utils import AioHTTPTestServer
        
        async with AioHTTPTestServer(app, port=8899) as server:
            print(f"📡 测试服务器启动: {server.make_url('/')}")
            
            # 等待服务器完全启动
            await asyncio.sleep(1)
            
            # 测试健康检查端点
            async with aiohttp.ClientSession() as session:
                test_url = server.make_url('/health')
                print(f"🔍 测试URL: {test_url}")
                
                # 测试简单请求
                print("📊 测试简单GET请求...")
                async with session.get(test_url) as resp:
                    print(f"  状态码: {resp.status}")
                    print(f"  响应头: {dict(resp.headers)}")
                    
                    if resp.status == 200:
                        print("✅ 健康检查端点正常")
                    else:
                        print(f"❌ 健康检查失败: {resp.status}")
                        return False
                
                # 测试带Origin的请求
                print("🌐 测试带Origin的请求...")
                async with session.get(
                    test_url,
                    headers={'Origin': 'https://test.example.com'}
                ) as resp:
                    print(f"  状态码: {resp.status}")
                    cors_origin = resp.headers.get('Access-Control-Allow-Origin')
                    cors_creds = resp.headers.get('Access-Control-Allow-Credentials')
                    print(f"  CORS Origin: {cors_origin}")
                    print(f"  CORS Credentials: {cors_creds}")
                    
                    if cors_origin:
                        print("✅ CORS头正确设置")
                        return True
                    else:
                        print("❌ CORS头缺失")
                        return False
                        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主函数"""
    print("🧪 简单CORS测试开始\n")
    
    success = await test_app_startup()
    
    if success:
        print("\n🎉 CORS测试成功！问题已修复")
        return 0
    else:
        print("\n❌ CORS测试失败，需要进一步调试")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  测试被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)