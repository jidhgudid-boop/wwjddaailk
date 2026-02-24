#!/usr/bin/env python3
"""
Browser file size display diagnostic
Tests different file sizes and response types to identify browser display issues
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware
from services.stream_proxy import StreamProxyService
from services.http_client import HTTPClientService
from models.config import config

def test_browser_display():
    """Test what browsers see in different scenarios"""
    print("=" * 70)
    print("浏览器文件大小显示诊断")
    print("=" * 70)
    
    # Create test files
    with tempfile.TemporaryDirectory() as tmpdir:
        # Small file (should use FileResponse)
        small_file = Path(tmpdir) / "small.txt"
        small_file.write_bytes(b'A' * (2 * 1024 * 1024))  # 2MB
        
        # Create test app
        app = FastAPI()
        
        # Add CORS like production
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["Content-Length", "Content-Range", "Accept-Ranges", "Content-Type"]
        )
        
        http_client_service = HTTPClientService()
        
        # Set config for filesystem mode
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
            
            client = TestClient(app)
            
            # Test 1: Small file (FileResponse path)
            print("\n[测试 1] 小文件（2MB - 应使用 FileResponse）")
            print("-" * 70)
            response = client.get("/small.txt")
            
            print(f"状态码: {response.status_code}")
            print(f"响应头:")
            for key, value in response.headers.items():
                if key.lower() in ['content-length', 'accept-ranges', 'content-type', 
                                   'cache-control', 'transfer-encoding', 'content-encoding']:
                    print(f"  {key}: {value}")
            
            # Check critical headers
            has_content_length = 'content-length' in response.headers
            has_transfer_encoding = 'transfer-encoding' in response.headers
            
            print(f"\n分析:")
            if has_content_length:
                print(f"  ✓ Content-Length: {response.headers['content-length']} 字节")
                print(f"  ✓ 浏览器应该能看到文件大小")
            else:
                print(f"  ✗ Content-Length: 未设置")
                print(f"  ✗ 浏览器可能看不到文件大小")
            
            if has_transfer_encoding:
                print(f"  ⚠ Transfer-Encoding: {response.headers['transfer-encoding']}")
                print(f"  ⚠ 这会导致浏览器不显示文件大小（chunked模式）")
            else:
                print(f"  ✓ Transfer-Encoding: 未使用")
            
            if 'accept-ranges' in response.headers:
                print(f"  ✓ Accept-Ranges: {response.headers['accept-ranges']}")
            
            # Test 2: Check if it's a Starlette/FastAPI issue
            print("\n[测试 2] 检查 FastAPI/Starlette 行为")
            print("-" * 70)
            
            # Get raw response to see what TestClient provides
            print(f"实际内容长度: {len(response.content)} 字节")
            print(f"Content-Length 头: {response.headers.get('content-length', 'N/A')}")
            
            if response.headers.get('content-length') == str(len(response.content)):
                print("  ✓ Content-Length 与实际内容匹配")
            else:
                print("  ✗ Content-Length 不匹配！")
            
            print("\n[诊断结论]")
            print("-" * 70)
            if has_content_length and not has_transfer_encoding:
                print("✓ 服务器端配置正确")
                print("✓ Content-Length 已正确设置")
                print("✓ 未使用 chunked 传输编码")
                print()
                print("如果浏览器仍然不显示文件大小，可能的原因：")
                print("  1. 反向代理（如 Nginx）修改了响应头")
                print("  2. 浏览器缓存问题（尝试硬刷新 Ctrl+Shift+R）")
                print("  3. 浏览器下载 UI 的设计（某些浏览器不总是显示）")
                print("  4. 使用了 HTTP/2（在开发工具 Network 标签可见）")
                print()
                print("建议:")
                print("  • 打开浏览器开发者工具 (F12)")
                print("  • 切换到 Network 标签")
                print("  • 查看请求的 Response Headers")
                print("  • 确认是否有 Content-Length")
            else:
                print("✗ 配置有问题！")
                if not has_content_length:
                    print("  • Content-Length 未设置")
                if has_transfer_encoding:
                    print("  • 使用了 Transfer-Encoding (chunked)")
                print()
                print("需要检查:")
                print("  • FileResponse 是否正确传递 headers")
                print("  • 中间件是否修改了响应")
            
        finally:
            config.BACKEND_MODE = original_mode
            config.BACKEND_FILESYSTEM_ROOT = original_root

if __name__ == "__main__":
    test_browser_display()
