#!/usr/bin/env python3
"""
Test script to verify Content-Length header in filesystem mode
"""
import sys
import os
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create a test file
test_dir = tempfile.mkdtemp()
test_file = Path(test_dir) / "test.ts"
test_content = b"X" * 3145728  # 3MB test file
test_file.write_bytes(test_content)

print(f"Created test file: {test_file}")
print(f"File size: {len(test_content)} bytes ({len(test_content) / (1024 * 1024):.2f} MB)")

# Test the headers
from services.stream_proxy import StreamProxyService

class MockHTTPClient:
    pass

class MockRequest:
    def __init__(self, has_range=False, range_header=None):
        self.has_range = has_range
        self.range_header = range_header
        self._headers = {}
        if range_header:
            self._headers["Range"] = range_header
    
    @property
    def headers(self):
        return self._headers
    
    async def is_disconnected(self):
        return False

# Mock config
import models.config as config_module
original_root = config_module.config.BACKEND_FILESYSTEM_ROOT
config_module.config.BACKEND_FILESYSTEM_ROOT = test_dir
config_module.config.BACKEND_FILESYSTEM_SENDFILE = False  # Force streaming

try:
    service = StreamProxyService(MockHTTPClient())
    
    # Test 1: Normal request (no Range)
    print("\n" + "="*70)
    print("Test 1: Normal request (no Range header)")
    print("="*70)
    
    import asyncio
    async def test_normal():
        mock_request = MockRequest()
        response = await service.proxy_filesystem(
            file_path="test.ts",
            request=mock_request,
            chunk_size=65536
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Type: {type(response).__name__}")
        
        if hasattr(response, 'headers'):
            print(f"Headers: {dict(response.headers)}")
            
            # Check critical headers
            content_length = response.headers.get('content-length')
            accept_ranges = response.headers.get('accept-ranges')
            
            print(f"\nContent-Length: {content_length}")
            print(f"Accept-Ranges: {accept_ranges}")
            
            if content_length:
                print(f"✓ PASS: Content-Length is set to {content_length} bytes")
                if int(content_length) == len(test_content):
                    print(f"✓ PASS: Content-Length matches file size")
                else:
                    print(f"✗ FAIL: Content-Length {content_length} doesn't match file size {len(test_content)}")
            else:
                print(f"✗ FAIL: Content-Length is NOT set!")
            
            if accept_ranges:
                print(f"✓ PASS: Accept-Ranges is set to '{accept_ranges}'")
            else:
                print(f"✗ FAIL: Accept-Ranges is NOT set!")
        else:
            print("✗ FAIL: Response has no headers attribute!")
        
        return response
    
    # Test 2: Range request
    print("\n" + "="*70)
    print("Test 2: Range request (bytes=0-1048575, first 1MB)")
    print("="*70)
    
    async def test_range():
        mock_request = MockRequest(has_range=True, range_header="bytes=0-1048575")
        response = await service.proxy_filesystem(
            file_path="test.ts",
            request=mock_request,
            chunk_size=65536
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Type: {type(response).__name__}")
        
        if hasattr(response, 'headers'):
            print(f"Headers: {dict(response.headers)}")
            
            content_length = response.headers.get('content-length')
            content_range = response.headers.get('content-range')
            
            print(f"\nContent-Length: {content_length}")
            print(f"Content-Range: {content_range}")
            
            if response.status_code == 206:
                print(f"✓ PASS: Status code is 206 (Partial Content)")
            else:
                print(f"✗ FAIL: Expected 206, got {response.status_code}")
            
            if content_length == "1048576":
                print(f"✓ PASS: Content-Length is correct for range (1MB)")
            else:
                print(f"✗ FAIL: Content-Length {content_length} incorrect for 1MB range")
            
            if content_range:
                print(f"✓ PASS: Content-Range is set: {content_range}")
            else:
                print(f"✗ FAIL: Content-Range is NOT set!")
    
    # Run tests
    asyncio.run(test_normal())
    asyncio.run(test_range())
    
    print("\n" + "="*70)
    print("Summary:")
    print("If Content-Length is not set for normal requests, clients cannot:")
    print("  - Show download progress (no total size)")
    print("  - Resume downloads (needs to know file size)")
    print("  - Verify download completion")
    print("="*70)
    
finally:
    # Cleanup
    config_module.config.BACKEND_FILESYSTEM_ROOT = original_root
    test_file.unlink()
    os.rmdir(test_dir)
    print(f"\nCleaned up test file: {test_file}")
