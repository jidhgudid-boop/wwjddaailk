#!/usr/bin/env python3
"""
Test HEAD request support for file proxy
Verifies that HEAD requests work correctly and return proper headers
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

def test_head_request():
    """Test HEAD request returns proper headers without body"""
    print("=" * 70)
    print("HEAD 请求支持测试")
    print("=" * 70)
    
    # Create test files
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = Path(tmpdir) / "test_video.mp4"
        test_content = b'A' * (5 * 1024 * 1024)  # 5MB file
        test_file.write_bytes(test_content)
        
        # Create test app
        app = FastAPI()
        
        # Add CORS
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
            
            # Simple test endpoint with GET and HEAD support
            @app.get("/{path:path}")
            @app.head("/{path:path}")
            async def test_proxy(request: Request, path: str):
                return await stream_proxy.proxy_stream(
                    file_path=path,
                    request=request,
                    chunk_size=config.STREAM_CHUNK_SIZE,
                    uid="test_user",
                    file_type="default"
                )
            
            client = TestClient(app)
            
            # Test 1: GET request (baseline)
            print("\n[测试 1] GET 请求 (基准)")
            print("-" * 70)
            get_response = client.get("/test_video.mp4")
            
            print(f"状态码: {get_response.status_code}")
            print(f"Content-Length: {get_response.headers.get('content-length', 'N/A')}")
            print(f"Accept-Ranges: {get_response.headers.get('accept-ranges', 'N/A')}")
            print(f"响应体大小: {len(get_response.content)} 字节")
            
            # Test 2: HEAD request
            print("\n[测试 2] HEAD 请求")
            print("-" * 70)
            head_response = client.head("/test_video.mp4")
            
            print(f"状态码: {head_response.status_code}")
            print(f"Content-Length: {head_response.headers.get('content-length', 'N/A')}")
            print(f"Accept-Ranges: {head_response.headers.get('accept-ranges', 'N/A')}")
            print(f"响应体大小: {len(head_response.content)} 字节")
            
            # Verification
            print("\n[验证结果]")
            print("-" * 70)
            
            success = True
            
            # Check GET request
            if get_response.status_code == 200:
                print("✓ GET 请求返回 200")
            else:
                print(f"✗ GET 请求返回 {get_response.status_code}（应该是 200）")
                success = False
            
            # Check HEAD request
            if head_response.status_code == 200:
                print("✓ HEAD 请求返回 200")
            else:
                print(f"✗ HEAD 请求返回 {head_response.status_code}（应该是 200）")
                success = False
            
            # Check Content-Length matches
            get_cl = get_response.headers.get('content-length')
            head_cl = head_response.headers.get('content-length')
            
            if get_cl and head_cl and get_cl == head_cl:
                print(f"✓ Content-Length 一致: {get_cl} 字节")
            else:
                print(f"✗ Content-Length 不一致: GET={get_cl}, HEAD={head_cl}")
                success = False
            
            # Check HEAD has no body
            if len(head_response.content) == 0:
                print("✓ HEAD 响应没有 body（正确）")
            else:
                print(f"✗ HEAD 响应有 body: {len(head_response.content)} 字节（应该为 0）")
                success = False
            
            # Check GET has body
            if len(get_response.content) == len(test_content):
                print(f"✓ GET 响应有完整 body: {len(get_response.content)} 字节")
            else:
                print(f"✗ GET 响应 body 大小不对: {len(get_response.content)} (应该是 {len(test_content)})")
                success = False
            
            # Check Accept-Ranges
            if head_response.headers.get('accept-ranges') == 'bytes':
                print("✓ HEAD 响应包含 Accept-Ranges: bytes")
            else:
                print(f"⚠ HEAD 响应 Accept-Ranges: {head_response.headers.get('accept-ranges', 'N/A')}")
            
            print("\n" + "=" * 70)
            if success:
                print("✓ 所有测试通过！HEAD 请求支持正常")
                print("\n现在可以使用 curl -I 来查看文件头信息：")
                print("  curl -I http://your-server/path/to/file.mp4")
            else:
                print("✗ 部分测试失败")
            print("=" * 70)
            
            return success
            
        finally:
            config.BACKEND_MODE = original_mode
            config.BACKEND_FILESYSTEM_ROOT = original_root

if __name__ == "__main__":
    import sys
    success = test_head_request()
    sys.exit(0 if success else 1)
