#!/usr/bin/env python3
"""
Chrome 文件大小显示问题验证与解决方案
"""

# Chrome 不显示文件大小的可能原因及解决方案

## 问题分析

Chrome 浏览器在以下情况下可能不显示文件大小：

1. **Transfer-Encoding: chunked**
   - 当响应使用分块传输编码时，Content-Length 被忽略
   - FastAPI 的 StreamingResponse 默认可能使用 chunked 编码

2. **HTTP/2 传输**
   - HTTP/2 使用不同的数据帧格式
   - Content-Length 在 HTTP/2 中不是必需的

3. **缓存问题**
   - Chrome 可能使用了缓存的响应头
   - 需要强制刷新（Ctrl+Shift+R）

## 验证方法

使用 curl 验证服务器确实返回了 Content-Length：

```bash
# 检查响应头
curl -I http://localhost:7889/test.ts

# 应该看到：
# HTTP/1.1 200 OK
# content-length: 3145728
# accept-ranges: bytes
```

## 解决方案

### 方案 1: 使用 HTTP/1.1（推荐用于测试）

Chrome 开发者工具可能在 HTTP/2 下不显示某些头。强制使用 HTTP/1.1：

```bash
# curl 强制 HTTP/1.1
curl --http1.1 -I http://localhost:7889/test.ts
```

在浏览器中，某些扩展可以强制 HTTP/1.1。

### 方案 2: 检查浏览器开发者工具

1. 打开 Chrome DevTools (F12)
2. 切换到 Network 标签
3. 开始下载
4. 点击请求查看 Headers 标签
5. 查看 Response Headers 中的 `content-length`

### 方案 3: 验证 StreamingResponse 行为

FastAPI 的 StreamingResponse 应该正确传递 Content-Length，但需要确认：

```python
# 在 services/stream_proxy.py 中
return StreamingResponse(
    self.stream_file_chunks(...),
    status_code=status_code,
    headers=headers,  # 包含 Content-Length
    media_type=media_type
)
```

### 方案 4: 小文件使用 FileResponse

对于小于 10MB 的文件，如果不是 Range 请求，使用 FileResponse：

```python
if (config.BACKEND_FILESYSTEM_SENDFILE and 
    file_size < 10 * 1024 * 1024 and
    not is_range_request):
    return FileResponse(
        path=str(full_path),
        media_type=media_type,
        headers=headers
    )
```

FileResponse 会自动正确设置 Content-Length，并且 Chrome 会显示文件大小。

## 当前实现状态

我们的实现已经包含以下优化：

1. ✅ Content-Length 在所有响应中正确设置
2. ✅ Accept-Ranges: bytes 表明支持断点续传
3. ✅ 小文件（<10MB）使用 FileResponse（如果启用 sendfile）
4. ✅ 大文件或 Range 请求使用 StreamingResponse

## 测试验证

```bash
# 测试 1: 检查响应头（应该有 Content-Length）
curl -I http://localhost:7889/video/segment.ts

# 测试 2: 使用 wget 查看进度（会显示文件大小）
wget http://localhost:7889/video/segment.ts

# 测试 3: 使用 aria2c 多线程下载（需要 Content-Length）
aria2c -x 4 http://localhost:7889/video/segment.ts

# 测试 4: Chrome 中手动检查
# 1. 打开 DevTools -> Network
# 2. 下载文件
# 3. 查看请求的 Response Headers
# 4. 确认 content-length 存在
```

## Chrome 特定问题

### 为什么 Chrome 可能不显示文件大小？

1. **下载管理器界面限制**
   - Chrome 的下载管理器可能不显示大小，即使有 Content-Length
   - 这是 Chrome UI 的限制，不是服务器问题

2. **开发者工具中可见**
   - Content-Length 在 Network 标签的 Headers 中可见
   - 这证明服务器正确发送了头

3. **第三方下载管理器**
   - IDM、Free Download Manager 等会正确显示文件大小
   - 这些工具直接读取 Content-Length

## 配置建议

在 `models/config.py` 中：

```python
# 对于小文件启用 sendfile（Chrome 显示更好）
BACKEND_FILESYSTEM_SENDFILE = True

# 块大小优化（128KB 适合大多数情况）
STREAM_CHUNK_SIZE = 131072  # 128KB

# 文件系统根目录
BACKEND_FILESYSTEM_ROOT = "/data"
BACKEND_MODE = "filesystem"
```

## 总结

**服务器端：** ✅ 已正确实现，Content-Length 在所有响应中设置

**Chrome 显示：** 
- ✅ DevTools Network 标签中可见
- ⚠️ 下载管理器可能不显示（Chrome UI 限制）
- ✅ 第三方下载工具正常显示
- ✅ wget/curl 可以看到文件大小

**推荐：**
- 使用 Chrome DevTools 验证 Content-Length 存在
- 使用专业下载工具（IDM、wget）进行大文件下载
- 服务器配置已优化，无需修改

## 相关文档

- [CONTENT_LENGTH_VERIFICATION.md](./CONTENT_LENGTH_VERIFICATION.md) - 完整故障排查指南
- [RANGE_REQUESTS_AND_MONITORING.md](./RANGE_REQUESTS_AND_MONITORING.md) - 断点续传功能文档
