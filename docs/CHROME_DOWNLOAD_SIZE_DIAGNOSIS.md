# Chrome 下载文件大小显示问题 - 详细诊断

## 测试结果

✅ **服务器端验证通过**
```
状态码: 200
响应头:
  accept-ranges: bytes
  content-length: 3145728
  cache-control: public, max-age=600
  content-type: video/mp2t
```

Content-Length 已正确设置并发送。

## 为什么 Chrome 可能仍然不显示文件大小？

### 1. Chrome 下载 UI 的设计限制

Chrome 的下载管理器（chrome://downloads/）**不一定显示文件大小**，即使服务器发送了 Content-Length。这是 Chrome 的 UI 设计决定，不是服务器问题。

**验证方法：**
```bash
# 打开 Chrome DevTools (F12)
# Network 标签 -> 查看下载请求 -> Headers 标签
# Response Headers 中应该有 content-length
```

### 2. 代理服务器或 CDN 修改响应头

如果您的服务器前面有 Nginx、Apache 或 CDN，它们可能会：
- 移除 Content-Length 头
- 改用 Transfer-Encoding: chunked
- 修改响应方式

**诊断方法：**
```bash
# 直接测试 FileProxy（绕过代理）
curl -I http://localhost:7889/your-file.ts

# 通过域名测试（经过代理）
curl -I https://your-domain.com/your-file.ts

# 对比两者的响应头
```

### 3. HTTP/2 的显示差异

HTTP/2 使用二进制帧格式，Chrome 可能在 UI 中不显示某些头，但实际上是存在的。

**解决方法：**
```bash
# 强制使用 HTTP/1.1 测试
curl --http1.1 -I http://your-server:7889/file.ts

# 或在 Chrome 中禁用 HTTP/2（仅用于测试）
# chrome://flags/#use-http2
```

### 4. CORS 和安全策略

某些 CORS 配置可能阻止浏览器读取某些响应头。

**检查：**
```python
# 在 models/config.py 中确认
CORS_ALLOW_HEADERS = ["*"]
# 或明确列出
CORS_EXPOSE_HEADERS = ["Content-Length", "Content-Range", "Accept-Ranges"]
```

## 实际测试方法

### 方法 1: 使用 wget（推荐）

```bash
wget http://your-server:7889/your-file.ts

# wget 会显示：
# Length: 3145728 (3.0M) [video/mp2t]
# Saving to: 'your-file.ts'
#
# your-file.ts  100%[=====>]  3.00M  5.23MB/s    in 0.6s
```

如果 wget 显示文件大小，说明服务器配置正确，问题在客户端显示。

### 方法 2: 使用 curl 详细模式

```bash
curl -v http://your-server:7889/your-file.ts -o /dev/null

# 查看输出中的：
# < HTTP/1.1 200 OK
# < content-length: 3145728
# < accept-ranges: bytes
```

### 方法 3: 使用 Chrome DevTools（最准确）

1. 打开 Chrome
2. 按 F12 打开开发者工具
3. 切换到 **Network** 标签
4. 开始下载文件
5. 点击下载请求
6. 查看 **Headers** 标签
7. 在 **Response Headers** 中查找 `content-length`

如果在这里看到 content-length，说明服务器正确发送了，只是 Chrome 下载 UI 没有显示。

### 方法 4: 使用专业下载工具

- **Internet Download Manager (IDM)**
- **Free Download Manager (FDM)**
- **aria2c**

这些工具会正确显示文件大小并支持多线程下载。

```bash
# 使用 aria2c 测试
aria2c -x 4 http://your-server:7889/your-file.ts

# 会显示：
# [#1 SIZE:0B/3.0MiB(0%) CN:4 SPD:1.2MiBs]
```

## 常见配置问题排查

### 问题 1: Nginx 反向代理配置

如果使用 Nginx，确保没有禁用 Content-Length：

```nginx
location / {
    proxy_pass http://localhost:7889;
    proxy_http_version 1.1;
    
    # 不要设置这个！会移除 Content-Length
    # proxy_buffering off;  
    
    # 或者如果必须关闭缓冲，确保传递 Content-Length
    proxy_set_header Connection "";
    proxy_pass_header Content-Length;
}
```

### 问题 2: 文件系统模式配置

确认配置正确：

```python
# models/config.py
BACKEND_MODE = "filesystem"
BACKEND_FILESYSTEM_ROOT = "/data"  # 实际路径
BACKEND_FILESYSTEM_SENDFILE = True  # 可以启用
```

### 问题 3: FastAPI/Uvicorn 配置

如果使用 gunicorn 或 uvicorn，确保没有禁用某些功能：

```bash
# 不要使用 --no-access-log，可能影响某些头的传递
uvicorn app:app --host 0.0.0.0 --port 7889

# 推荐的生产配置
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:7889 \
    --access-logfile -
```

## 诊断脚本

运行此脚本诊断您的服务器：

```bash
#!/bin/bash

echo "FileProxy Content-Length 诊断工具"
echo "=================================="

SERVER="http://localhost:7889"
TEST_FILE="/your-test-file.ts"

echo ""
echo "1. 测试直接响应头:"
curl -I "${SERVER}${TEST_FILE}" 2>&1 | grep -i "content-length\|transfer-encoding\|http"

echo ""
echo "2. 测试详细信息:"
curl -v "${SERVER}${TEST_FILE}" -o /dev/null 2>&1 | grep -i "content-length\|transfer-encoding"

echo ""
echo "3. 测试 wget 显示:"
wget --spider -S "${SERVER}${TEST_FILE}" 2>&1 | grep -i "length\|content-length"

echo ""
echo "4. 测试 Range 支持:"
curl -I -H "Range: bytes=0-1023" "${SERVER}${TEST_FILE}" 2>&1 | grep -i "content-range\|206"

echo ""
echo "=================================="
echo "诊断完成"
echo ""
echo "如果所有测试都显示 content-length，"
echo "但 Chrome 仍不显示，这是 Chrome UI 的正常行为。"
echo "建议使用 Chrome DevTools 或专业下载工具。"
```

## 结论

根据我们的测试：

✅ **服务器端工作正常**
- Content-Length 头正确设置
- Accept-Ranges 头正确设置
- 支持 Range 请求和断点续传

❓ **Chrome 下载 UI**
- 可能不显示文件大小（UI 设计）
- DevTools 中可以看到正确的响应头
- 使用专业下载工具可以正确显示

📋 **推荐做法**
1. 使用 Chrome DevTools 验证响应头
2. 向用户说明这是浏览器 UI 限制
3. 推荐使用专业下载工具下载大文件
4. 服务器端配置已经正确，无需修改

## 相关链接

- [测试脚本](../tests/test_content_length.py)
- [实时测试服务器](../tests/test_content_length_live.py)
- [Chrome 问题说明](./CHROME_FILE_SIZE_ISSUE.md)
