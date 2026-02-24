#!/usr/bin/env python3
"""
Quick test server to verify Content-Length headers are visible to clients
Run this and test with: curl -I http://localhost:8899/test.ts
"""
import os
import sys
import tempfile
from pathlib import Path

# Create a test file
TEST_DIR = Path(tempfile.mkdtemp())
TEST_FILE = TEST_DIR / "test.ts"
TEST_FILE.write_bytes(b"X" * (3 * 1024 * 1024))  # 3MB file

print(f"Created test file: {TEST_FILE}")
print(f"File size: {TEST_FILE.stat().st_size} bytes")

# Minimal FastAPI app to test
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.stream_proxy import StreamProxyService
from models import config

# Configure for filesystem mode
config.config.BACKEND_MODE = "filesystem"
config.config.BACKEND_FILESYSTEM_ROOT = str(TEST_DIR)
config.config.BACKEND_FILESYSTEM_SENDFILE = False  # Force streaming to test headers

app = FastAPI()

class MockHTTPClient:
    pass

stream_service = StreamProxyService(MockHTTPClient())

@app.get("/{path:path}")
async def proxy(path: str, request: Request):
    """Test proxy endpoint"""
    response = await stream_service.proxy_filesystem(
        file_path=path,
        request=request,
        chunk_size=65536
    )
    return response

@app.get("/")
async def root():
    return {
        "message": "Test server running",
        "test_file": str(TEST_FILE.name),
        "file_size": TEST_FILE.stat().st_size,
        "test_commands": [
            f"curl -I http://localhost:8899/{TEST_FILE.name}",
            f"curl -H 'Range: bytes=0-1048575' -I http://localhost:8899/{TEST_FILE.name}",
            f"wget --spider http://localhost:8899/{TEST_FILE.name}"
        ]
    }

if __name__ == "__main__":
    print("\n" + "="*70)
    print("Test Server Started!")
    print("="*70)
    print("\nTest with these commands:")
    print(f"  curl -I http://localhost:8899/{TEST_FILE.name}")
    print(f"  curl -H 'Range: bytes=0-1048575' -I http://localhost:8899/{TEST_FILE.name}")
    print(f"  wget --spider http://localhost:8899/{TEST_FILE.name}")
    print("\nPress Ctrl+C to stop")
    print("="*70 + "\n")
    
    try:
        uvicorn.run(app, host="0.0.0.0", port=8899, log_level="info")
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Cleanup
        TEST_FILE.unlink()
        TEST_DIR.rmdir()
        print(f"Cleaned up test file")
