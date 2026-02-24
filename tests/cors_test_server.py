#!/usr/bin/env python3
"""
简化版应用，仅用于测试 aiohttp_cors 功能，不需要 Redis
"""

from aiohttp import web
import aiohttp_cors
import json
import time
import os

async def health_check(request):
    """健康检查端点"""
    return web.json_response({
        "status": "healthy",
        "timestamp": int(time.time()),
        "cors_library": "aiohttp_cors",
        "message": "CORS test endpoint working",
        "worker_pid": os.getpid()
    })

async def api_test(request):
    """API测试端点"""
    origin = request.headers.get('Origin', 'unknown')
    user_agent = request.headers.get('User-Agent', 'unknown')
    
    return web.json_response({
        "method": request.method,
        "origin": origin,
        "user_agent": user_agent[:100] + "..." if len(user_agent) > 100 else user_agent,
        "timestamp": int(time.time()),
        "headers": dict(request.headers),
        "query": dict(request.query),
        "message": "CORS API test successful"
    })

def create_test_app():
    """创建测试应用"""
    app = web.Application()
    
    # 配置 CORS - 允许任何来源
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*", 
            allow_headers="*",
            allow_methods="*"
        )
    })
    
    # 添加路由并配置CORS - aiohttp_cors会自动处理OPTIONS
    cors.add(app.router.add_route("GET", "/health", health_check))
    cors.add(app.router.add_route("GET", "/api/test", api_test))
    cors.add(app.router.add_route("POST", "/api/test", api_test))
    
    return app

if __name__ == '__main__':
    print("🚀 启动 CORS 测试服务器...")
    app = create_test_app()
    web.run_app(app, host='127.0.0.1', port=7888)