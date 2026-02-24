#!/usr/bin/env python3
"""
Test to verify Content-Length is sent even with StreamingResponse
"""
from starlette.responses import StreamingResponse
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Route

async def generate_chunks():
    """Simple generator that yields chunks"""
    for i in range(5):
        yield b"chunk" + str(i).encode()

async def test_endpoint(request):
    """Test endpoint with StreamingResponse"""
    headers = {
        "Content-Length": "25",  # 5 chunks * 5 bytes
        "Accept-Ranges": "bytes"
    }
    return StreamingResponse(
        generate_chunks(),
        headers=headers,
        media_type="text/plain"
    )

app = Starlette(routes=[Route("/test", test_endpoint)])

# Test it
client = TestClient(app)
response = client.get("/test")

print("Status:", response.status_code)
print("Headers:", dict(response.headers))
print("Content-Length in headers:", "content-length" in response.headers)
print("Transfer-Encoding in headers:", "transfer-encoding" in response.headers)
print("Content:", response.content)
print("Actual content length:", len(response.content))

if "content-length" in response.headers:
    print("\n✓ Content-Length IS preserved in StreamingResponse")
else:
    print("\n✗ Content-Length NOT preserved - using chunked encoding")
    if "transfer-encoding" in response.headers:
        print(f"  Transfer-Encoding: {response.headers['transfer-encoding']}")
