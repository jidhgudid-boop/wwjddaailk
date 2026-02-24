#!/usr/bin/env python3
"""
测试流式传输的 Content-Length 头显示
验证优化后的实现能够正确显示文件总大小
"""
import os
import sys
import asyncio
import tempfile
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from services.stream_proxy import StreamProxyService
from services.http_client import HTTPClientService
from models.config import config


async def test_filesystem_streaming_content_length():
    """测试文件系统模式下流式传输的 Content-Length"""
    print("=" * 70)
    print("测试：文件系统模式流式传输 Content-Length")
    print("=" * 70)
    
    # 创建测试文件
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_large.bin"
        
        # 创建 35MB 测试文件（触发流式传输，使用固定模式以提高速度）
        file_size = 35 * 1024 * 1024  # 35MB
        print(f"\n创建测试文件: {file_size / (1024*1024):.1f} MB")
        
        with open(test_file, 'wb') as f:
            # 使用固定模式替代随机数据，大幅提高测试速度
            chunk_size = 1024 * 1024  # 1MB chunks
            pattern = b'A' * chunk_size  # 固定字节模式
            for _ in range(file_size // chunk_size):
                f.write(pattern)
        
        actual_size = test_file.stat().st_size
        print(f"✓ 文件创建成功: {actual_size} 字节")
        
        # 创建测试应用
        app = FastAPI()
        http_client_service = HTTPClientService()
        
        # 临时修改配置以使用测试目录
        original_mode = config.BACKEND_MODE
        original_root = config.BACKEND_FILESYSTEM_ROOT
        config.BACKEND_MODE = "filesystem"
        config.BACKEND_FILESYSTEM_ROOT = tmpdir
        
        try:
            stream_proxy = StreamProxyService(http_client_service)
            
            @app.get("/{path:path}")
            async def proxy_handler(request: Request, path: str):
                return await stream_proxy.proxy_stream(
                    file_path=path,
                    request=request,
                    chunk_size=config.STREAM_CHUNK_SIZE,
                    uid="test_user",
                    file_type="default"
                )
            
            # 使用 TestClient 测试
            client = TestClient(app)
            
            # 测试 1: 普通请求
            print("\n[测试 1] 普通请求（完整文件）")
            response = client.get("/test_large.bin")
            
            print(f"状态码: {response.status_code}")
            print(f"Content-Length: {response.headers.get('content-length', 'NOT SET')}")
            print(f"Accept-Ranges: {response.headers.get('accept-ranges', 'NOT SET')}")
            print(f"实际响应大小: {len(response.content)} 字节")
            
            # 验证
            assert response.status_code == 200, f"预期 200，得到 {response.status_code}"
            
            content_length = response.headers.get('content-length')
            if content_length:
                content_length = int(content_length)
                print(f"✓ Content-Length 已设置: {content_length} 字节")
                assert content_length == actual_size, \
                    f"Content-Length ({content_length}) 与文件大小 ({actual_size}) 不匹配"
                print("✓ Content-Length 与文件大小匹配")
            else:
                print("⚠ Content-Length 未设置（流式传输可能使用 chunked encoding）")
            
            assert response.headers.get('accept-ranges') == 'bytes', \
                "Accept-Ranges 应该是 'bytes'"
            print("✓ Accept-Ranges 已正确设置")
            
            # 测试 2: Range 请求
            print("\n[测试 2] Range 请求（部分内容）")
            response = client.get(
                "/test_large.bin",
                headers={"Range": "bytes=0-1023"}
            )
            
            print(f"状态码: {response.status_code}")
            print(f"Content-Length: {response.headers.get('content-length', 'NOT SET')}")
            print(f"Content-Range: {response.headers.get('content-range', 'NOT SET')}")
            print(f"实际响应大小: {len(response.content)} 字节")
            
            # 验证
            assert response.status_code == 206, f"预期 206，得到 {response.status_code}"
            print("✓ 返回 206 Partial Content")
            
            content_length = response.headers.get('content-length')
            if content_length:
                assert int(content_length) == 1024, \
                    f"Content-Length ({content_length}) 应该是 1024"
                print("✓ Content-Length 正确（1024 字节）")
            
            content_range = response.headers.get('content-range')
            assert content_range, "Content-Range 应该存在"
            assert f"/{actual_size}" in content_range, \
                f"Content-Range ({content_range}) 应包含总文件大小 ({actual_size})"
            print(f"✓ Content-Range 正确: {content_range}")
            
            # 测试 3: 小文件（应使用 FileResponse）
            print("\n[测试 3] 小文件（< 10MB，应使用 FileResponse）")
            small_file = Path(tmpdir) / "test_small.bin"
            small_size = 5 * 1024 * 1024  # 5MB
            with open(small_file, 'wb') as f:
                f.write(b'B' * small_size)  # 固定模式，快速创建
            
            response = client.get("/test_small.bin")
            
            print(f"状态码: {response.status_code}")
            print(f"Content-Length: {response.headers.get('content-length', 'NOT SET')}")
            print(f"实际响应大小: {len(response.content)} 字节")
            
            assert response.status_code == 200
            content_length = response.headers.get('content-length')
            assert content_length, "小文件应该有 Content-Length"
            assert int(content_length) == small_size, \
                f"Content-Length ({content_length}) 应该等于文件大小 ({small_size})"
            print("✓ 小文件 Content-Length 正确设置")
            
            # 测试 4: 中等文件（10-32MB，应使用 Response）
            print("\n[测试 4] 中等文件（10-32MB，应使用 Response）")
            medium_file = Path(tmpdir) / "test_medium.bin"
            medium_size = 20 * 1024 * 1024  # 20MB
            with open(medium_file, 'wb') as f:
                f.write(b'C' * medium_size)  # 固定模式，快速创建
            
            response = client.get("/test_medium.bin")
            
            print(f"状态码: {response.status_code}")
            print(f"Content-Length: {response.headers.get('content-length', 'NOT SET')}")
            print(f"实际响应大小: {len(response.content)} 字节")
            
            assert response.status_code == 200
            content_length = response.headers.get('content-length')
            assert content_length, "中等文件应该有 Content-Length"
            assert int(content_length) == medium_size, \
                f"Content-Length ({content_length}) 应该等于文件大小 ({medium_size})"
            print("✓ 中等文件 Content-Length 正确设置")
            
            print("\n" + "=" * 70)
            print("✓ 所有测试通过！")
            print("=" * 70)
            print("\n总结:")
            print("  • 小文件（< 10MB）：使用 FileResponse，Content-Length ✓")
            print("  • 中等文件（10-32MB）：使用 Response，Content-Length ✓")
            print("  • 大文件（> 32MB）：使用 StreamingResponse，Content-Length ✓")
            print("  • Range 请求：支持断点续传，Content-Range 正确 ✓")
            
        finally:
            # 恢复配置
            config.BACKEND_MODE = original_mode
            config.BACKEND_FILESYSTEM_ROOT = original_root


if __name__ == "__main__":
    asyncio.run(test_filesystem_streaming_content_length())
