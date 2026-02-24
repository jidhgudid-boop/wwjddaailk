#!/usr/bin/env python3
"""
测试 aiohttp_cors 库是否正确处理 CORS 请求
"""

import aiohttp
import asyncio
import time
import json

async def test_cors_headers():
    """测试不同来源的CORS请求"""
    
    print("🧪 测试 aiohttp_cors 库的 CORS 处理...")
    
    # 测试的来源列表
    test_origins = [
        "https://v.yuelk.com",
        "https://v-upload.yuelk.com", 
        "http://localhost:3000",
        "https://test.example.com",
        "https://any-random-domain.com",
        None  # 无 Origin 头的请求
    ]
    
    base_url = "http://127.0.0.1:7888"
    
    async with aiohttp.ClientSession() as session:
        for origin in test_origins:
            print(f"\n📡 测试来源: {origin or '(无 Origin 头)'}")
            
            # 构建请求头
            headers = {}
            if origin:
                headers['Origin'] = origin
            
            try:
                # 测试 OPTIONS 预检请求
                print("  🔍 测试 OPTIONS 预检请求...")
                async with session.options(
                    f"{base_url}/health",
                    headers=headers
                ) as resp:
                    print(f"    状态码: {resp.status}")
                    cors_headers = {
                        'Access-Control-Allow-Origin': resp.headers.get('Access-Control-Allow-Origin'),
                        'Access-Control-Allow-Methods': resp.headers.get('Access-Control-Allow-Methods'),
                        'Access-Control-Allow-Headers': resp.headers.get('Access-Control-Allow-Headers'),
                        'Access-Control-Allow-Credentials': resp.headers.get('Access-Control-Allow-Credentials'),
                    }
                    print(f"    CORS 头: {json.dumps(cors_headers, indent=6, ensure_ascii=False)}")
                
                # 测试实际 GET 请求
                print("  📥 测试 GET 请求...")
                async with session.get(
                    f"{base_url}/health",
                    headers=headers
                ) as resp:
                    print(f"    状态码: {resp.status}")
                    cors_headers = {
                        'Access-Control-Allow-Origin': resp.headers.get('Access-Control-Allow-Origin'),
                        'Access-Control-Allow-Credentials': resp.headers.get('Access-Control-Allow-Credentials'),
                        'Vary': resp.headers.get('Vary')
                    }
                    print(f"    CORS 头: {json.dumps(cors_headers, indent=6, ensure_ascii=False)}")
                    
                    if resp.status == 200:
                        print("    ✅ 请求成功")
                    else:
                        print(f"    ❌ 请求失败，状态: {resp.status}")
                        
            except Exception as e:
                print(f"    ❌ 请求异常: {str(e)}")
    
    print(f"\n🎯 测试完成!")

async def test_specific_cors_scenarios():
    """测试特定的CORS场景"""
    
    print("\n🔬 测试特定CORS场景...")
    
    base_url = "http://127.0.0.1:7888"
    
    async with aiohttp.ClientSession() as session:
        # 场景1：跨域预检请求，包含自定义头
        print("\n📋 场景1: 带自定义头的预检请求")
        headers = {
            'Origin': 'https://custom-app.example.com',
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'Authorization, X-Session-ID'
        }
        
        try:
            async with session.options(f"{base_url}/health", headers=headers) as resp:
                print(f"  状态码: {resp.status}")
                print(f"  允许的方法: {resp.headers.get('Access-Control-Allow-Methods')}")
                print(f"  允许的头: {resp.headers.get('Access-Control-Allow-Headers')}")
                print(f"  允许的来源: {resp.headers.get('Access-Control-Allow-Origin')}")
        except Exception as e:
            print(f"  ❌ 异常: {str(e)}")
        
        # 场景2：带认证的跨域请求
        print("\n🔐 场景2: 带认证的跨域请求")
        headers = {
            'Origin': 'https://auth-app.example.com',
            'Authorization': 'Bearer test-token',
            'X-Session-ID': 'test-session-123'
        }
        
        try:
            async with session.get(f"{base_url}/health", headers=headers) as resp:
                print(f"  状态码: {resp.status}")
                print(f"  允许认证: {resp.headers.get('Access-Control-Allow-Credentials')}")
                print(f"  允许的来源: {resp.headers.get('Access-Control-Allow-Origin')}")
        except Exception as e:
            print(f"  ❌ 异常: {str(e)}")

if __name__ == "__main__":
    print("🚀 启动 CORS 测试...")
    print("⚠️  确保服务器正在 http://127.0.0.1:7888 上运行")
    print("   你可以运行: python app.py")
    
    time.sleep(2)  # 给用户时间看到说明
    
    try:
        asyncio.run(test_cors_headers())
        asyncio.run(test_specific_cors_scenarios())
    except KeyboardInterrupt:
        print("\n👋 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")