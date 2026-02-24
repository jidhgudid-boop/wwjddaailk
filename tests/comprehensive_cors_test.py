#!/usr/bin/env python3
"""
完整的 CORS 验证测试，模拟浏览器行为
"""

import aiohttp
import asyncio
import json
import time

async def test_cors_comprehensive():
    """完整的 CORS 测试，模拟真实浏览器行为"""
    
    print("🌐 完整的 CORS 验证测试")
    print("=" * 50)
    
    base_url = "http://127.0.0.1:7888"
    
    # 测试场景
    test_scenarios = [
        {
            "name": "生产环境主域名",
            "origin": "https://v.yuelk.com",
            "description": "主要生产域名"
        },
        {
            "name": "生产环境上传域名", 
            "origin": "https://v-upload.yuelk.com",
            "description": "上传功能域名"
        },
        {
            "name": "本地开发环境",
            "origin": "http://localhost:3000",
            "description": "本地 React/Vue 开发服务器"
        },
        {
            "name": "本地开发环境(8080)",
            "origin": "http://localhost:8080", 
            "description": "本地 Vue CLI 开发服务器"
        },
        {
            "name": "测试环境",
            "origin": "https://test.staging.example.com",
            "description": "测试/预发布环境"
        },
        {
            "name": "第三方集成",
            "origin": "https://partner.example.com",
            "description": "第三方合作伙伴域名"
        },
        {
            "name": "CDN域名",
            "origin": "https://cdn.yuelk.com",
            "description": "CDN资源域名"
        }
    ]
    
    async with aiohttp.ClientSession() as session:
        
        for scenario in test_scenarios:
            print(f"\n📋 测试场景: {scenario['name']}")
            print(f"   Origin: {scenario['origin']}")
            print(f"   描述: {scenario['description']}")
            
            # 1. 测试简单请求（GET /health）
            print("   🔍 简单 GET 请求...")
            try:
                headers = {'Origin': scenario['origin']}
                async with session.get(f"{base_url}/health", headers=headers) as resp:
                    cors_origin = resp.headers.get('Access-Control-Allow-Origin')
                    cors_credentials = resp.headers.get('Access-Control-Allow-Credentials')
                    
                    if resp.status == 200:
                        if cors_origin == scenario['origin']:
                            print(f"     ✅ 状态: {resp.status}, Origin 匹配: {cors_origin}")
                        else:
                            print(f"     ❌ 状态: {resp.status}, Origin 不匹配: 期望 {scenario['origin']}, 实际 {cors_origin}")
                        
                        if cors_credentials == 'true':
                            print("     ✅ 允许认证信息")
                        else:
                            print(f"     ❌ 认证信息配置错误: {cors_credentials}")
                    else:
                        print(f"     ❌ 请求失败，状态码: {resp.status}")
                        
            except Exception as e:
                print(f"     ❌ 请求异常: {str(e)}")
            
            # 2. 测试预检请求（模拟浏览器发起的 CORS 预检）
            print("   🔬 CORS 预检请求...")
            try:
                preflight_headers = {
                    'Origin': scenario['origin'],
                    'Access-Control-Request-Method': 'GET',
                    'Access-Control-Request-Headers': 'Authorization, Content-Type, X-Session-ID'
                }
                
                async with session.options(f"{base_url}/health", headers=preflight_headers) as resp:
                    allow_origin = resp.headers.get('Access-Control-Allow-Origin')
                    allow_methods = resp.headers.get('Access-Control-Allow-Methods')
                    allow_headers = resp.headers.get('Access-Control-Allow-Headers')
                    allow_credentials = resp.headers.get('Access-Control-Allow-Credentials')
                    
                    if resp.status == 200:
                        print(f"     ✅ 预检成功，状态: {resp.status}")
                        print(f"     📋 允许来源: {allow_origin}")
                        print(f"     📋 允许方法: {allow_methods}")
                        print(f"     📋 允许头部: {allow_headers}")
                        print(f"     📋 允许认证: {allow_credentials}")
                    else:
                        print(f"     ❌ 预检失败，状态: {resp.status}")
                        
            except Exception as e:
                print(f"     ❌ 预检异常: {str(e)}")
            
            # 3. 测试带认证的请求
            print("   🔐 带认证的请求...")
            try:
                auth_headers = {
                    'Origin': scenario['origin'],
                    'Authorization': 'Bearer test-token-123',
                    'X-Session-ID': 'session-abc-456',
                    'Content-Type': 'application/json'
                }
                
                async with session.get(f"{base_url}/health", headers=auth_headers) as resp:
                    if resp.status == 200:
                        cors_origin = resp.headers.get('Access-Control-Allow-Origin')
                        if cors_origin == scenario['origin']:
                            print(f"     ✅ 认证请求成功，Origin: {cors_origin}")
                        else:
                            print(f"     ❌ 认证请求 Origin 不匹配: {cors_origin}")
                    else:
                        print(f"     ❌ 认证请求失败，状态: {resp.status}")
                        
            except Exception as e:
                print(f"     ❌ 认证请求异常: {str(e)}")
        
        # 4. 测试特殊场景
        print(f"\n🎯 特殊场景测试")
        print("-" * 30)
        
        # 无 Origin 头的请求
        print("📝 无 Origin 头的请求...")
        try:
            async with session.get(f"{base_url}/health") as resp:
                cors_origin = resp.headers.get('Access-Control-Allow-Origin')
                print(f"   状态: {resp.status}, CORS Origin: {cors_origin or '(未设置)'}")
        except Exception as e:
            print(f"   ❌ 异常: {str(e)}")
        
        # 测试 POST 请求
        print("📝 POST 请求测试...")
        try:
            headers = {
                'Origin': 'https://test.example.com',
                'Content-Type': 'application/json',
                'Authorization': 'Bearer F2UkWEJZRBxC7'
            }
            data = {
                "uid": "test-uid",
                "path": "/test/path.m3u8", 
                "clientIp": "192.168.1.100",
                "UserAgent": "Mozilla/5.0 Test Browser"
            }
            
            async with session.post(f"{base_url}/api/whitelist", 
                                  headers=headers, 
                                  json=data) as resp:
                cors_origin = resp.headers.get('Access-Control-Allow-Origin')
                print(f"   状态: {resp.status}, CORS Origin: {cors_origin}")
                if resp.status == 200:
                    result = await resp.json()
                    print(f"   ✅ POST 请求成功")
                else:
                    print(f"   ⚠️  POST 请求状态: {resp.status}")
                    
        except Exception as e:
            print(f"   ❌ POST 异常: {str(e)}")

    print(f"\n🎉 CORS 验证测试完成!")
    print("=" * 50)

async def test_real_world_scenarios():
    """测试真实世界的使用场景"""
    
    print("\n🌍 真实世界场景测试")
    print("=" * 50)
    
    base_url = "http://127.0.0.1:7888"
    
    # 模拟前端应用的实际请求模式
    scenarios = [
        {
            "name": "前端应用加载视频列表",
            "origin": "https://v.yuelk.com",
            "requests": [
                {"method": "GET", "path": "/health", "description": "健康检查"},
                {"method": "GET", "path": "/stats", "description": "获取统计信息"}
            ]
        },
        {
            "name": "本地开发调试",
            "origin": "http://localhost:3000", 
            "requests": [
                {"method": "GET", "path": "/debug/browser", "description": "浏览器检测调试"},
                {"method": "GET", "path": "/debug/session", "description": "会话调试"},
                {"method": "GET", "path": "/traffic", "description": "流量统计"}
            ]
        }
    ]
    
    async with aiohttp.ClientSession() as session:
        for scenario in scenarios:
            print(f"\n🎬 场景: {scenario['name']}")
            print(f"   Origin: {scenario['origin']}")
            
            for req in scenario['requests']:
                print(f"   📡 {req['description']} ({req['method']} {req['path']})")
                
                try:
                    headers = {'Origin': scenario['origin']}
                    url = f"{base_url}{req['path']}"
                    
                    if req['method'] == 'GET':
                        async with session.get(url, headers=headers) as resp:
                            cors_origin = resp.headers.get('Access-Control-Allow-Origin')
                            print(f"      状态: {resp.status}, CORS: {cors_origin}")
                            if cors_origin == scenario['origin']:
                                print("      ✅ CORS 配置正确")
                            else:
                                print(f"      ❌ CORS 问题: 期望 {scenario['origin']}, 实际 {cors_origin}")
                                
                except Exception as e:
                    print(f"      ❌ 请求失败: {str(e)}")

if __name__ == "__main__":
    print("🚀 启动完整 CORS 验证...")
    print("⚠️  确保服务器运行在 http://127.0.0.1:7888")
    
    time.sleep(2)  # 给用户时间看到说明
    
    try:
        asyncio.run(test_cors_comprehensive())
        asyncio.run(test_real_world_scenarios())
    except KeyboardInterrupt:
        print("\n👋 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")