# Content-Length 在生产环境中不显示 - 故障排查

## 问题描述

用户报告：通过实际服务器 (http://spcs.yuelk.com:7889) 下载文件时，浏览器仍然不显示文件总大小，即使：
- 服务器代码已正确设置 Content-Length
- 测试环境（TestClient）验证 Content-Length 存在
- 未使用反向代理

## 根本原因

**ASGI 服务器（uvicorn/gunicorn）在使用 StreamingResponse 时可能会：**
1. 移除 Content-Length 头
2. 使用 `Transfer-Encoding: chunked` 替代
3. 这是为了安全和一致性考虑的默认行为

### 为什么会这样？

当使用生成器（generator）作为响应体时，ASGI 服务器无法预先知道响应的总大小，因此默认使用分块传输编码（chunked transfer encoding）。即使我们手动设置了 Content-Length，服务器也可能忽略或覆盖它。

## 解决方案

### 方案 1: 对于已知大小的文件，避免使用 StreamingResponse 的生成器

最可靠的方法是不使用生成器，而是一次性读取文件并发送：

```python
# 不推荐（当前实现）- 使用生成器
return StreamingResponse(
    self.stream_file_chunks(...),  # 生成器
    headers=headers
)

# 推荐 - 对于中小文件使用 FileResponse
if file_size < 50 * 1024 * 1024:  # 50MB
    return FileResponse(
        path=str(full_path),
        headers=headers,
        media_type=media_type
    )
```

### 方案 2: 修改 uvicorn/gunicorn 配置

某些 ASGI 服务器配置可能影响 Content-Length 的处理。

**uvicorn 配置：**
```bash
# 使用 HTTP/1.1（不使用 HTTP/2）
uvicorn app:app --host 0.0.0.0 --port 7889 --loop uvloop

# 不要使用这些选项（可能导致问题）
# --no-access-log
# --proxy-headers (除非真的需要)
```

**gunicorn 配置：**
```python
# gunicorn_fastapi.conf.py
import multiprocessing

bind = "0.0.0.0:7889"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
keepalive = 65

# 确保不禁用这些
accesslog = "-"
errorlog = "-"
```

### 方案 3: 使用自定义中间件强制保留 Content-Length

创建中间件确保 Content-Length 不被移除：

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

class ContentLengthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # 对于文件下载，确保 Content-Length 存在
        if request.url.path.endswith(('.ts', '.m3u8', '.mp4', '.bin')):
            # 如果响应有 transfer-encoding，尝试移除它
            if 'transfer-encoding' in response.headers:
                # 注意：这可能不总是有效
                pass
        
        return response

# 在 app.py 中添加
app.add_middleware(ContentLengthMiddleware)
```

### 方案 4: 修改 StreamingResponse 实现（推荐）

修改代码以提供实际的字节内容而非生成器：

```python
# 在 services/stream_proxy.py 中添加新方法

async def read_file_with_range(
    self,
    file_path: Path,
    start_byte: int = 0,
    end_byte: int = None
) -> bytes:
    """
    读取文件的指定范围（用于小文件）
    对于大文件应继续使用流式传输
    """
    async with aiofiles.open(file_path, mode='rb') as f:
        if start_byte > 0:
            await f.seek(start_byte)
        
        if end_byte is not None:
            size_to_read = end_byte - start_byte + 1
            return await f.read(size_to_read)
        else:
            return await f.read()

# 然后修改 proxy_filesystem 方法
async def proxy_filesystem(self, ...):
    # ... 现有代码 ...
    
    # 对于小文件（<10MB），使用 Response 而非 StreamingResponse
    if content_length < 10 * 1024 * 1024:  # 10MB
        logger.debug(f"使用 Response (非流式): {full_path.name}, size={content_length}")
        
        # 读取文件内容
        file_content = await self.read_file_with_range(
            full_path,
            start_byte=start_byte,
            end_byte=end_byte
        )
        
        return Response(
            content=file_content,
            status_code=status_code,
            headers=headers,
            media_type=media_type
        )
    else:
        # 大文件继续使用 StreamingResponse
        return StreamingResponse(...)
```

## 当前代码的问题

查看当前实现：

```python
# services/stream_proxy.py 第 491-506 行
return StreamingResponse(
    self.stream_file_chunks(  # <-- 这是生成器
        file_path=full_path,
        request=request,
        chunk_size=chunk_size,
        uid=uid,
        session_id=session_id,
        file_type=file_type,
        client_ip=client_ip,
        start_byte=start_byte,
        end_byte=end_byte
    ),
    status_code=status_code,
    headers=headers,  # <-- Content-Length 在这里
    media_type=media_type
)
```

**问题：** `stream_file_chunks` 是一个异步生成器，ASGI 服务器看到生成器后会：
1. 忽略 Content-Length
2. 自动使用 `Transfer-Encoding: chunked`
3. 结果：浏览器看不到文件大小

## 立即可用的解决方案

### 快速修复：提高 FileResponse 使用阈值

当前代码只对 <10MB 的文件使用 FileResponse。提高这个限制：

```python
# 在 proxy_filesystem 方法中
use_streaming = (
    is_range_request or
    not config.BACKEND_FILESYSTEM_SENDFILE or
    file_size >= 50 * 1024 * 1024  # 改为 50MB 而非 10MB
)

if not use_streaming:
    # 使用 FileResponse - 这个会正确设置 Content-Length
    return FileResponse(...)
```

### 验证修复

修改后，测试：

```bash
# 检查响应头
curl -I http://your-server:7889/wp-content/uploads/bigfile.bin

# 应该看到 Content-Length 而不是 Transfer-Encoding: chunked

# 使用 wget 测试
wget http://your-server:7889/wp-content/uploads/bigfile.bin
# 应该显示文件大小：Length: XXXXXX (XX MB)
```

## 调试步骤

### 1. 检查实际响应头

```bash
curl -v http://spcs.yuelk.com:7889/wp-content/uploads/bigfile.bin \
  -o /dev/null 2>&1 | grep -E "< HTTP|< Content-Length|< Transfer-Encoding"
```

### 2. 检查文件大小

```bash
# 在服务器上
ls -lh /data/wp-content/uploads/bigfile.bin

# 检查是否超过 10MB（当前 FileResponse 阈值）
```

### 3. 查看服务器日志

```bash
tail -f logs/proxy_fastapi.log | grep "bigfile.bin"

# 查找这两个关键日志：
# "使用 FileResponse (sendfile):" - 好，会有 Content-Length
# "使用流式传输:" - 可能有问题，ASGI 服务器可能使用 chunked
```

### 4. 测试不同文件大小

```bash
# 创建小文件测试（<10MB）
dd if=/dev/zero of=/data/test_small.bin bs=1M count=5

# 创建大文件测试（>10MB）
dd if=/dev/zero of=/data/test_large.bin bs=1M count=20

# 测试两者
curl -I http://your-server:7889/test_small.bin
curl -I http://your-server:7889/test_large.bin

# 比较响应头差异
```

## 推荐的修复

基于分析，推荐实施**方案 4**：修改代码使用 Response 而非 StreamingResponse 处理小到中等文件。

这是最可靠的解决方案，因为：
1. ✅ 保证 Content-Length 被保留
2. ✅ 浏览器能正确显示文件大小
3. ✅ 支持断点续传（Range 请求）
4. ✅ 对于大文件仍使用流式传输（节省内存）

## 临时解决方法

如果无法修改代码，用户可以：

1. **使用专业下载工具**
   - wget, curl, aria2c, IDM, FDM
   - 这些工具不依赖 Content-Length 显示大小

2. **使用 Chrome DevTools 查看**
   - F12 → Network → 点击请求
   - 查看实际传输了多少字节

3. **等待下载完成**
   - 即使不显示大小，下载仍然正常工作

## 相关文档

- [Chrome 文件大小诊断](./CHROME_DOWNLOAD_SIZE_DIAGNOSIS.md)
- [Content-Length 验证指南](./CONTENT_LENGTH_VERIFICATION.md)
- [测试模式配置](./TEST_MODE_CONFIG.md)
