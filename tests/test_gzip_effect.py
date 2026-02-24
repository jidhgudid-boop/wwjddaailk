#!/usr/bin/env python3
"""
测试 GZip 中间件对 Content-Length 的影响
演示为什么必须禁用 GZip 才能显示下载进度
"""
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import Response
from fastapi.testclient import TestClient

print("=" * 70)
print("GZip 中间件对 Content-Length 的影响测试")
print("=" * 70)

# Test 1: 不使用 GZip 中间件
print("\n[测试 1] 没有 GZip 中间件")
print("-" * 70)

app1 = FastAPI()

@app1.get("/file")
async def get_file():
    content = b"A" * (2 * 1024 * 1024)  # 2MB 文件
    return Response(
        content=content,
        headers={
            "Content-Length": str(len(content)),
            "Accept-Ranges": "bytes"
        },
        media_type="video/mp4"
    )

client1 = TestClient(app1)
response1 = client1.get("/file")

print(f"状态码: {response1.status_code}")
print(f"Content-Length: {response1.headers.get('content-length', 'NOT SET')}")
print(f"Transfer-Encoding: {response1.headers.get('transfer-encoding', 'NOT SET')}")
print(f"Content-Encoding: {response1.headers.get('content-encoding', 'NOT SET')}")
print(f"实际内容大小: {len(response1.content)} 字节")

has_cl1 = 'content-length' in response1.headers
has_te1 = 'transfer-encoding' in response1.headers

if has_cl1 and not has_te1:
    print("✓ 浏览器可以显示文件大小和下载进度")
else:
    print("✗ 浏览器无法显示文件大小和下载进度")

# Test 2: 使用 GZip 中间件
print("\n[测试 2] 启用 GZip 中间件")
print("-" * 70)

app2 = FastAPI()
app2.add_middleware(GZipMiddleware, minimum_size=1000)

@app2.get("/file")
async def get_file2():
    content = b"A" * (2 * 1024 * 1024)  # 2MB 文件
    return Response(
        content=content,
        headers={
            "Content-Length": str(len(content)),
            "Accept-Ranges": "bytes"
        },
        media_type="video/mp4"
    )

client2 = TestClient(app2)
response2 = client2.get("/file")

print(f"状态码: {response2.status_code}")
print(f"Content-Length: {response2.headers.get('content-length', 'NOT SET')}")
print(f"Transfer-Encoding: {response2.headers.get('transfer-encoding', 'NOT SET')}")
print(f"Content-Encoding: {response2.headers.get('content-encoding', 'NOT SET')}")
print(f"实际内容大小: {len(response2.content)} 字节 (压缩后)")

has_cl2 = 'content-length' in response2.headers
has_te2 = 'transfer-encoding' in response2.headers

if has_cl2 and not has_te2:
    print("✓ 浏览器可以显示文件大小和下载进度")
else:
    print("✗ 浏览器无法显示文件大小和下载进度")

# Summary
print("\n" + "=" * 70)
print("测试总结")
print("=" * 70)

print(f"\n没有 GZip:")
print(f"  Content-Length: {'存在' if has_cl1 else '不存在'}")
print(f"  Transfer-Encoding: {'存在 (chunked)' if has_te1 else '不存在'}")
print(f"  浏览器显示进度: {'✓ 可以' if (has_cl1 and not has_te1) else '✗ 不可以'}")

print(f"\n启用 GZip:")
print(f"  Content-Length: {'存在' if has_cl2 else '不存在'}")
print(f"  Transfer-Encoding: {'存在 (chunked)' if has_te2 else '不存在'}")
print(f"  浏览器显示进度: {'✓ 可以' if (has_cl2 and not has_te2) else '✗ 不可以'}")

print("\n结论:")
if has_cl1 and not has_cl2:
    print("✓ GZip 中间件移除了 Content-Length 头")
    print("✓ 这就是浏览器无法显示下载进度的原因！")
    print("\n解决方案: 禁用 GZip 中间件（ENABLE_GZIP_COMPRESSION = False）")
else:
    print("需要进一步调查...")

print("=" * 70)
