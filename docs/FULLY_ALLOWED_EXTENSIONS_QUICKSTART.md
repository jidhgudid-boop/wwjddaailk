# 快速开始：完全放行文件扩展名配置

## 什么是完全放行文件扩展名？

完全放行文件扩展名（Fully Allowed Extensions）是一个配置选项，允许您指定哪些文件类型可以跳过所有安全验证，直接由服务器代理。这对于已知安全的静态资源（如 HLS 视频分片、图片等）可以显著提升性能。

## 快速配置

### 1. 编辑配置文件

打开 `models/config.py`，找到 `FULLY_ALLOWED_EXTENSIONS` 配置：

```python
# 完全放行的文件扩展名配置（这些文件类型将完全跳过所有验证，直接放行）
FULLY_ALLOWED_EXTENSIONS = (
    '.ts',    # HLS 视频分片
    '.webp',  # WebP 图片
    '.php'    # PHP 文件（向后兼容）
)
```

### 2. 自定义扩展名

根据您的需求修改配置。例如：

**仅放行 HLS 视频分片**:
```python
FULLY_ALLOWED_EXTENSIONS = ('.ts',)
```

**放行多种图片格式**:
```python
FULLY_ALLOWED_EXTENSIONS = (
    '.ts',      # HLS 视频分片
    '.webp',    # WebP 图片
    '.jpg',     # JPEG 图片
    '.png',     # PNG 图片
)
```

**放行所有常见静态资源**:
```python
FULLY_ALLOWED_EXTENSIONS = (
    '.ts', '.webp', '.jpg', '.jpeg', '.png', '.gif', '.svg',  # 视频和图片
    '.css', '.js',                                            # 样式和脚本
    '.woff', '.woff2', '.ttf', '.eot',                       # 字体
    '.ico', '.txt'                                           # 其他
)
```

### 3. 重启服务

修改配置后，重启服务以使配置生效：

```bash
# 如果使用 systemd
sudo systemctl restart fileproxy

# 如果手动运行
pkill -f "python.*app.py"
python app.py

# 或者使用 gunicorn
pkill gunicorn
gunicorn -c gunicorn_fastapi.conf.py app:app
```

## 验证配置

### 1. 运行测试

```bash
cd /home/runner/work/YuemPyScripts/YuemPyScripts/Server/FileProxy
python3 tests/test_fully_allowed_extensions.py
```

应该看到所有测试通过：
```
✅ 所有测试通过!
```

### 2. 测试实际请求

使用 curl 测试不同类型的文件：

```bash
# 测试 .ts 文件（应该跳过验证）
curl -I http://localhost:7889/video/segment.ts

# 测试 .webp 文件（应该跳过验证）
curl -I http://localhost:7889/image/photo.webp

# 测试 .m3u8 文件（应该需要验证）
curl -I http://localhost:7889/playlist/master.m3u8
```

### 3. 查看日志

检查服务日志，确认配置正确加载：

```bash
tail -f logs/proxy_fastapi.log | grep -i "FULLY_ALLOWED"
```

## 常见场景

### 场景 1: HLS 流媒体服务

如果您主要提供 HLS 流媒体服务，推荐配置：

```python
FULLY_ALLOWED_EXTENSIONS = (
    '.ts',    # HLS 视频分片（由 m3u8 文件的验证保护）
    '.webp',  # 缩略图和海报
)
```

**原因**: .ts 文件本身是视频片段，安全性由 .m3u8 播放列表的 HMAC 验证保护，可以安全地跳过验证以提升性能。

### 场景 2: 图片 CDN 服务

如果主要提供图片服务，推荐配置：

```python
FULLY_ALLOWED_EXTENSIONS = (
    '.webp', '.jpg', '.jpeg', '.png', '.gif', '.svg',  # 所有图片格式
)
```

### 场景 3: 完整的 Web 应用

如果需要代理完整的 Web 应用，推荐配置：

```python
FULLY_ALLOWED_EXTENSIONS = (
    '.ts', '.webp', '.jpg', '.jpeg', '.png', '.gif', '.svg',  # 媒体文件
    '.css', '.js',                                            # 前端资源
    '.woff', '.woff2', '.ttf',                               # 字体文件
    '.ico', '.txt', '.xml', '.json'                          # 其他静态资源
)
```

## 安全建议

⚠️ **重要**: 完全放行的文件不会进行任何验证，请谨慎配置。

### ✅ 适合放行的文件类型

- **公开的媒体文件**: .ts, .webp, .jpg, .png
- **前端静态资源**: .css, .js, .woff
- **已通过其他方式保护的文件**: 例如 .ts 文件由 .m3u8 的 HMAC 验证保护

### ❌ 不应放行的文件类型

- **播放列表文件**: .m3u8 - 需要 HMAC 验证
- **加密密钥**: .key, enc.key - 必须验证
- **包含敏感信息的文件**: 用户数据、配置文件等

## 性能优势

启用完全放行后，这些文件类型的请求将跳过：
- ✅ Redis 查询（IP 白名单检查）
- ✅ 路径匹配计算
- ✅ 会话验证逻辑
- ✅ HMAC 签名验证

**预期性能提升**: 20-40% 的请求处理速度提升

## 故障排查

### 问题 1: 配置不生效

**症状**: 修改配置后文件仍然需要验证

**解决方法**:
1. 确认已重启服务
2. 检查配置格式（元组，每个元素以点开头）
3. 查看日志确认配置加载
4. 确认 `ENABLE_STATIC_FILE_IP_ONLY_CHECK = True`

### 问题 2: 所有请求都跳过验证

**症状**: 所有请求都不验证，包括不应该放行的

**解决方法**:
1. 检查 `ENABLE_STATIC_FILE_IP_ONLY_CHECK` 的值
2. 确认 `FULLY_ALLOWED_EXTENSIONS` 不包含过多扩展名
3. 检查是否误设置了测试模式配置（DISABLE_IP_WHITELIST 等）

### 问题 3: 性能没有提升

**症状**: 启用放行后性能没有明显变化

**原因及解决**:
1. 确认放行的文件类型占据大部分请求（查看监控面板）
2. 检查是否有其他性能瓶颈（Redis、网络、磁盘 I/O）
3. 使用 `/monitor` 查看跳过验证的请求统计

## 更多信息

- 完整文档: [FULLY_ALLOWED_EXTENSIONS.md](FULLY_ALLOWED_EXTENSIONS.md)
- 配置文件: `models/config.py`
- 测试文件: `tests/test_fully_allowed_extensions.py`
- 问题反馈: 在 GitHub 上创建 Issue

## 示例：逐步启用

如果不确定应该放行哪些文件，可以逐步启用：

**第 1 步**: 仅放行最常见的 .ts 文件
```python
FULLY_ALLOWED_EXTENSIONS = ('.ts',)
```

**第 2 步**: 观察 1-2 天，确认没有问题后添加图片
```python
FULLY_ALLOWED_EXTENSIONS = ('.ts', '.webp', '.jpg')
```

**第 3 步**: 继续观察，再添加其他静态资源
```python
FULLY_ALLOWED_EXTENSIONS = (
    '.ts', '.webp', '.jpg', '.jpeg', '.png',
    '.css', '.js', '.woff', '.woff2'
)
```

通过逐步启用，可以在确保安全的同时获得性能提升。
