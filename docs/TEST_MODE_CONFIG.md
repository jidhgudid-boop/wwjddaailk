# 测试模式配置指南

## 概述

为了方便开发和测试，FileProxy 提供了可以禁用安全检查的配置选项。**这些选项仅用于开发和测试环境，生产环境必须保持禁用。**

## 配置选项

在 `models/config.py` 中添加了以下测试模式配置：

```python
# 测试模式配置（用于开发和测试，生产环境应设为 False）
DISABLE_IP_WHITELIST = False  # 设为 True 跳过 IP 白名单检查
DISABLE_PATH_PROTECTION = False  # 设为 True 跳过路径保护检查
DISABLE_SESSION_VALIDATION = False  # 设为 True 跳过会话验证
```

## 使用场景

### 1. 本地开发测试

启用测试模式可以直接访问文件，无需配置 IP 白名单或会话：

```python
# models/config.py
DISABLE_IP_WHITELIST = True
DISABLE_PATH_PROTECTION = True
DISABLE_SESSION_VALIDATION = True
```

启用后，可以直接访问任何文件：
```bash
# 直接下载测试
curl http://localhost:7889/test/video.ts -o video.ts

# 浏览器访问
http://localhost:7889/test/video.ts
```

### 2. 性能测试

测试文件传输性能和 Range 请求支持时，可以禁用安全检查减少干扰：

```python
DISABLE_IP_WHITELIST = True
DISABLE_PATH_PROTECTION = True
# 保留会话验证以测试完整流程
DISABLE_SESSION_VALIDATION = False
```

### 3. Content-Length 验证测试

验证 Content-Length 头和断点续传功能：

```bash
# 启用测试模式后
export SERVER='http://localhost:7889'
export TEST_FILE='/path/to/test.ts'
./diagnose_content_length.sh
```

## 配置说明

### DISABLE_IP_WHITELIST

**作用：** 跳过 IP 白名单检查

**启用时：**
- 所有 IP 地址都允许访问
- 不再检查 Redis 中的 IP 白名单
- 自动使用 `test_user` 作为 UID

**日志输出：**
```
⚠️ 测试模式：跳过 IP 白名单检查 (DISABLE_IP_WHITELIST=True)
```

### DISABLE_PATH_PROTECTION

**作用：** 跳过路径保护检查

**启用时：**
- 所有路径都允许访问
- 不再检查路径是否在白名单中
- 与 DISABLE_IP_WHITELIST 配合使用

**日志输出：**
```
⚠️ 测试模式：跳过路径保护检查 (DISABLE_PATH_PROTECTION=True)
```

### DISABLE_SESSION_VALIDATION

**作用：** 跳过会话验证

**启用时：**
- 不再验证会话 cookie
- 不再检查会话是否有效
- 自动使用默认 UID

**日志输出：**
```
⚠️ 测试模式：跳过会话验证 (DISABLE_SESSION_VALIDATION=True)
```

## 快速启用测试模式

### 方法 1: 修改配置文件

编辑 `models/config.py`：

```python
# 测试模式配置（用于开发和测试，生产环境应设为 False）
DISABLE_IP_WHITELIST = True  # ✅ 启用
DISABLE_PATH_PROTECTION = True  # ✅ 启用
DISABLE_SESSION_VALIDATION = True  # ✅ 启用
```

保存后重启服务器：
```bash
# 如果使用 uvicorn
pkill -f uvicorn
python app.py

# 如果使用 gunicorn
pkill -f gunicorn
gunicorn -c gunicorn_fastapi.conf.py app:app
```

### 方法 2: 环境变量（推荐）

创建测试配置文件 `config_test.py`：

```python
from models.config import Config

class TestConfig(Config):
    """测试环境配置"""
    DISABLE_IP_WHITELIST = True
    DISABLE_PATH_PROTECTION = True
    DISABLE_SESSION_VALIDATION = True
    
    # 其他测试配置
    BACKEND_FILESYSTEM_ROOT = "/tmp/test_data"
    REDIS_DB = 15  # 使用不同的 Redis 数据库

# 在 app.py 中导入
# from config_test import TestConfig as Config
```

## 测试示例

### 测试 1: 直接文件下载

```bash
# 启用测试模式后
curl http://localhost:7889/videos/test.ts -o test.ts

# 验证下载
ls -lh test.ts
```

### 测试 2: Range 请求测试

```bash
# 测试部分下载
curl -H "Range: bytes=0-1048575" http://localhost:7889/videos/test.ts -o part1.ts

# 验证 206 响应
curl -I -H "Range: bytes=0-1048575" http://localhost:7889/videos/test.ts
```

### 测试 3: 断点续传测试

```bash
# 开始下载
wget http://localhost:7889/videos/large.ts

# 中断（Ctrl+C）

# 继续下载
wget -c http://localhost:7889/videos/large.ts
```

### 测试 4: 监控面板测试

```bash
# 访问监控面板
open http://localhost:7889/monitor

# 在另一个终端下载文件
curl http://localhost:7889/videos/test.ts -o test.ts

# 在监控面板观察实时传输进度
```

## 安全警告

⚠️ **重要：生产环境必须禁用测试模式**

```python
# 生产环境配置
DISABLE_IP_WHITELIST = False  # ❌ 必须为 False
DISABLE_PATH_PROTECTION = False  # ❌ 必须为 False
DISABLE_SESSION_VALIDATION = False  # ❌ 必须为 False
```

启用测试模式会：
- 允许任何 IP 访问
- 允许访问任何路径
- 跳过所有安全检查
- **严重的安全风险！**

## 生产环境检查清单

部署到生产环境前，确认：

- [ ] `DISABLE_IP_WHITELIST = False`
- [ ] `DISABLE_PATH_PROTECTION = False`
- [ ] `DISABLE_SESSION_VALIDATION = False`
- [ ] 已配置正确的 IP 白名单
- [ ] 已配置正确的路径权限
- [ ] SECRET_KEY 已更改为安全值
- [ ] Redis 密码已设置
- [ ] 日志中没有测试模式警告

## 查看日志

启用测试模式时，日志会显示警告：

```bash
tail -f logs/proxy_fastapi.log | grep "测试模式"
```

输出示例：
```
2025-10-31 10:00:00 [INFO] ⚠️ 测试模式：跳过 IP 白名单检查 (DISABLE_IP_WHITELIST=True)
2025-10-31 10:00:00 [INFO] ⚠️ 测试模式：跳过路径保护检查 (DISABLE_PATH_PROTECTION=True)
2025-10-31 10:00:00 [INFO] ⚠️ 测试模式：跳过会话验证 (DISABLE_SESSION_VALIDATION=True)
```

如果在生产环境看到这些日志，**立即禁用测试模式！**

## 故障排查

### 问题 1: 修改配置后不生效

**解决方法：**
```bash
# 确保重启了服务器
ps aux | grep -E "uvicorn|gunicorn|python.*app.py"
# 杀掉旧进程
pkill -f "uvicorn|gunicorn"
# 重新启动
python app.py
```

### 问题 2: 仍然返回 403

**检查：**
1. 确认配置文件被正确修改
2. 确认服务器已重启
3. 检查日志是否有测试模式消息
4. 确认没有其他安全检查（如 Nginx 限制）

### 问题 3: Redis 连接错误

**解决方法：**
```python
# 测试模式可以禁用某些 Redis 依赖
# 但 Redis 仍然需要运行
# 确认 Redis 服务正在运行
# systemctl status redis
# 或
# docker ps | grep redis
```

## 相关文档

- [Content-Length 诊断](./CHROME_DOWNLOAD_SIZE_DIAGNOSIS.md)
- [Range 请求文档](./RANGE_REQUESTS_AND_MONITORING.md)
- [主 README](../README.md)

## 总结

测试模式配置提供了便捷的开发和测试方式，但必须注意：

✅ **开发/测试环境：** 可以启用，方便快速测试
❌ **生产环境：** 必须禁用，确保安全性

使用时始终检查日志中的测试模式警告，确保在正确的环境中使用正确的配置。
