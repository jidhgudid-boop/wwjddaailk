#!/usr/bin/env python3
"""
实际 HTTP 测试 - 验证 Content-Length 在真实请求中是否正确发送
"""
import asyncio
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, '/home/runner/work/YuemPyScripts/YuemPyScripts/Server/FileProxy')

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn

# 创建测试文件
TEST_DIR = Path(tempfile.mkdtemp())
TEST_FILE = TEST_DIR / "test_download.ts"
TEST_CONTENT = b"X" * (5 * 1024 * 1024)  # 5MB 测试文件
TEST_FILE.write_bytes(TEST_CONTENT)

print(f"测试文件创建: {TEST_FILE}")
print(f"文件大小: {len(TEST_CONTENT)} bytes ({len(TEST_CONTENT) / (1024 * 1024):.2f} MB)")

# 导入服务
from services.stream_proxy import StreamProxyService
from models import config

# 配置
config.config.BACKEND_MODE = "filesystem"
config.config.BACKEND_FILESYSTEM_ROOT = str(TEST_DIR)
config.config.BACKEND_FILESYSTEM_SENDFILE = False  # 强制流式传输测试

app = FastAPI()

class MockHTTPClient:
    pass

stream_service = StreamProxyService(MockHTTPClient())

@app.get("/test.ts")
async def download_test(request: Request):
    """测试下载端点"""
    print(f"\n{'='*70}")
    print(f"收到下载请求: {request.url}")
    print(f"客户端 User-Agent: {request.headers.get('user-agent', 'unknown')}")
    print(f"Range 头: {request.headers.get('range', 'None')}")
    print(f"{'='*70}\n")
    
    response = await stream_service.proxy_filesystem(
        file_path="test_download.ts",
        request=request,
        chunk_size=65536  # 64KB chunks
    )
    
    # 打印响应头信息
    print(f"\n{'='*70}")
    print(f"响应状态: {response.status_code}")
    print(f"响应类型: {type(response).__name__}")
    if hasattr(response, 'headers'):
        print(f"响应头:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
    print(f"{'='*70}\n")
    
    return response

@app.get("/")
async def root():
    return {
        "message": "Content-Length 测试服务器",
        "test_file": "test.ts",
        "file_size": len(TEST_CONTENT),
        "test_commands": [
            "curl -I http://localhost:8900/test.ts",
            "curl -v http://localhost:8900/test.ts -o /dev/null",
            "wget --spider -S http://localhost:8900/test.ts 2>&1 | grep -i content-length"
        ]
    }

if __name__ == "__main__":
    print("\n" + "="*70)
    print("Content-Length 测试服务器启动")
    print("="*70)
    print("\n在另一个终端运行以下命令测试：\n")
    print("1. 查看响应头:")
    print("   curl -I http://localhost:8900/test.ts\n")
    print("2. 详细下载信息:")
    print("   curl -v http://localhost:8900/test.ts -o /dev/null\n")
    print("3. 使用 wget 测试:")
    print("   wget http://localhost:8900/test.ts\n")
    print("4. 浏览器测试:")
    print("   http://localhost:8900/test.ts\n")
    print("="*70 + "\n")
    
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8900,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n服务器关闭")
    finally:
        # 清理
        TEST_FILE.unlink()
        TEST_DIR.rmdir()
        print(f"已清理测试文件")
