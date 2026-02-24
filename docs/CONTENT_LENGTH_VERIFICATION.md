# 文件大小显示和断点续传验证指南

## 问题描述

用户反馈：在使用 filesystem 模式时，下载文件看不到文件大小，可能影响断点续传功能。

## 验证结果

经过测试验证，**Content-Length 头已经正确设置**。测试结果显示：

### 正常请求（无 Range 头）
```
Status Code: 200
Headers:
  - Content-Length: 3145728 (3MB)
  - Accept-Ranges: bytes
  - Content-Type: video/mp2t
✓ 文件大小正确显示
✓ 支持断点续传（Accept-Ranges: bytes）
```

### Range 请求（部分内容）
```
Status Code: 206 (Partial Content)
Headers:
  - Content-Length: 1048576 (1MB，请求的部分)
  - Content-Range: bytes 0-1048575/3145728
  - Accept-Ranges: bytes
✓ 部分内容大小正确
✓ 总文件大小在 Content-Range 中显示
```

## 可能的原因

如果您在下载时看不到文件大小，可能是以下原因：

### 1. 浏览器开发者工具查看方式

某些浏览器的开发者工具可能不显示流式响应的 Content-Length。

**解决方案：** 使用命令行工具验证：

```bash
# 检查响应头
curl -I http://your-server:7889/path/to/file.ts

# 应该看到：
# HTTP/1.1 200 OK
# content-length: 3145728
# accept-ranges: bytes
# content-type: video/mp2t
```

### 2. 小文件使用 FileResponse

对于小于 10MB 的文件，如果启用了 `BACKEND_FILESYSTEM_SENDFILE=True`，系统会使用 FileResponse。

**当前配置检查：**

```python
# 在 models/config.py 中检查
BACKEND_FILESYSTEM_SENDFILE = True  # 是否启用
```

**验证：** FileResponse 也会正确设置 Content-Length，但可以强制使用流式传输来测试：

```python
# 临时禁用 sendfile 测试
BACKEND_FILESYSTEM_SENDFILE = False
```

### 3. HTTP/2 传输编码

HTTP/2 可能使用不同的传输编码方式，不显示传统的 Content-Length。

**解决方案：** 使用 HTTP/1.1 测试：

```bash
curl --http1.1 -I http://your-server:7889/path/to/file.ts
```

### 4. 代理或 CDN 中间层

如果您的服务器前面有反向代理（如 Nginx）或 CDN，它们可能修改或删除 Content-Length 头。

**检查方法：**

```bash
# 直接访问 FileProxy 服务器（绕过代理）
curl -I http://localhost:7889/path/to/file.ts

# 通过代理访问
curl -I http://your-domain.com/path/to/file.ts

# 对比两个响应头
```

## 验证步骤

### 步骤 1: 启动测试服务器

```bash
cd /home/runner/work/YuemPyScripts/YuemPyScripts/Server/FileProxy
python tests/test_server_headers.py
```

### 步骤 2: 测试响应头

在另一个终端运行：

```bash
# 测试 1: 检查完整文件头
curl -I http://localhost:8899/test.ts

# 预期输出应包含：
# HTTP/1.1 200 OK
# content-length: 3145728
# accept-ranges: bytes

# 测试 2: 检查 Range 请求
curl -H "Range: bytes=0-1048575" -I http://localhost:8899/test.ts

# 预期输出应包含：
# HTTP/1.1 206 Partial Content
# content-length: 1048576
# content-range: bytes 0-1048575/3145728
# accept-ranges: bytes

# 测试 3: 使用 wget 测试断点续传
wget http://localhost:8899/test.ts
# 中断下载 (Ctrl+C)
wget -c http://localhost:8899/test.ts
# 应该从断点继续下载
```

### 步骤 3: 检查生产环境

```bash
# 替换为您的实际服务器地址和文件路径
SERVER="http://your-server:7889"
FILE_PATH="path/to/your/file.ts"

# 检查响应头
curl -I "$SERVER/$FILE_PATH"

# 检查是否支持 Range
curl -H "Range: bytes=0-1023" -I "$SERVER/$FILE_PATH"
```

## 预期行为

### 正确的响应头（200 OK）
```http
HTTP/1.1 200 OK
content-length: 3145728
accept-ranges: bytes
content-type: video/mp2t
cache-control: public, max-age=600
```

### 正确的响应头（206 Partial Content）
```http
HTTP/1.1 206 Partial Content
content-length: 1048576
content-range: bytes 0-1048575/3145728
accept-ranges: bytes
content-type: video/mp2t
cache-control: public, max-age=600
```

## 断点续传测试

### 使用 wget 测试

```bash
# 开始下载
wget http://your-server:7889/large_file.ts

# 中断下载 (Ctrl+C)

# 继续下载（-c 参数启用断点续传）
wget -c http://your-server:7889/large_file.ts

# wget 会发送 Range 头：
# Range: bytes=<已下载字节数>-
```

### 使用 curl 测试

```bash
# 下载前 1MB 并保存
curl -H "Range: bytes=0-1048575" http://your-server:7889/file.ts -o file.part1

# 下载第二个 1MB
curl -H "Range: bytes=1048576-2097151" http://your-server:7889/file.ts -o file.part2

# 合并文件
cat file.part1 file.part2 > file.ts

# 验证文件完整性
md5sum file.ts
```

### 使用下载管理器测试

大多数下载管理器（如 IDM、Free Download Manager）会自动使用 Range 请求来实现多线程下载和断点续传。

## 调试日志

查看服务器日志确认 Range 请求处理：

```bash
tail -f logs/proxy_fastapi.log | grep -E "Range|206|Content-Range"
```

应该看到类似的日志：

```
2025-10-31 09:00:00 [DEBUG] Range 请求: file.ts, range=1048576-2097151/3145728
2025-10-31 09:00:00 [DEBUG] 使用流式传输: file.ts, size=3145728, range=1048576-2097151, content_length=1048576
```

## 常见问题

### Q: 为什么浏览器下载时不显示进度？

**A:** 某些浏览器可能不显示流式下载的进度。尝试：
1. 使用开发者工具查看 Network 标签的响应头
2. 使用支持显示下载进度的浏览器插件
3. 使用专门的下载管理器

### Q: Content-Length 显示为 `transfer-encoding: chunked` 怎么办？

**A:** 如果看到 `transfer-encoding: chunked` 而不是 Content-Length，可能是：
1. 服务器使用了分块传输编码
2. 中间代理修改了响应头

这不影响断点续传功能，因为 Content-Range 头仍然包含文件总大小。

### Q: 断点续传仍然不工作怎么办？

**A:** 检查以下配置：

```python
# models/config.py
BACKEND_MODE = "filesystem"  # 必须是 filesystem
BACKEND_FILESYSTEM_ROOT = "/data"  # 确保路径正确
BACKEND_FILESYSTEM_SENDFILE = True  # 可以启用或禁用
```

确保文件存在且可读：

```bash
ls -lh /data/path/to/file.ts
```

## 总结

根据测试验证，FileProxy 的 Content-Length 头设置是正确的，支持：

✅ 完整文件下载时显示文件大小  
✅ Range 请求返回正确的部分内容大小  
✅ Content-Range 头包含完整文件大小  
✅ Accept-Ranges 头表明支持断点续传  
✅ wget -c 和下载管理器可以正常断点续传  

如果您仍然遇到问题，请：
1. 运行提供的测试脚本验证基础功能
2. 检查是否有反向代理或 CDN 修改响应头
3. 使用 curl 命令行工具验证实际的 HTTP 响应
4. 提供具体的响应头和日志以便进一步诊断

## 进一步帮助

如果问题持续存在，请提供以下信息：

1. curl 命令的完整输出：
   ```bash
   curl -v -I http://your-server:7889/file.ts
   ```

2. 服务器配置：
   ```bash
   grep -E "BACKEND_MODE|BACKEND_FILESYSTEM" models/config.py
   ```

3. 服务器日志相关部分：
   ```bash
   tail -100 logs/proxy_fastapi.log | grep -A 5 -B 5 "file.ts"
   ```
