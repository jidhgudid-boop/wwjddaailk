# 快速开始指南

## 🚀 5分钟快速启动

### 1. 安装依赖
```bash
cd Server/FileProxy
pip install -r requirements.txt
```

### 2. 配置 Redis
确保 Redis 正在运行：
```bash
redis-cli ping
# 应该返回: PONG
```

### 3. 启动服务器

**开发环境：**
```bash
python app.py
```

**生产环境：**
```bash
gunicorn -c gunicorn_fastapi.conf.py app:app
```

### 4. 验证服务

**健康检查：**
```bash
curl http://localhost:7889/health
```

**访问监控面板：**
```
http://localhost:7889/monitor
```

## 📋 使用示例

### 添加 IP 到白名单
```bash
curl -X POST http://localhost:7889/api/whitelist \
  -H "Authorization: Bearer F2UkWEJZRBxC7" \
  -H "Content-Type: application/json" \
  -d '{
    "uid": "user123",
    "path": "/video/2024-01-01/movie/playlist.m3u8",
    "clientIp": "192.168.1.100",
    "UserAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
  }'
```

**响应示例：**
```json
{
  "success": true,
  "message": "CIDR whitelist added/updated successfully",
  "key_path": "movie",
  "ip_pattern": "192.168.1.0/24",
  "cidr_examples": ["192.168.1.1", "192.168.1.2", "192.168.1.3"],
  "ua_hash": "a1b2c3d4",
  "ttl": 3600
}
```

### 访问受保护的文件

**生成 HMAC 令牌：**
```python
import hmac
import hashlib
import base64
import time

uid = "user123"
path = "/video/2024-01-01/movie/playlist.m3u8"
expires = str(int(time.time()) + 3600)  # 1小时后过期
secret_key = b"super_secret_key_change_this"

msg = f"{uid}:{path}:{expires}".encode()
token = base64.urlsafe_b64encode(
    hmac.new(secret_key, msg, hashlib.sha256).digest()
).decode().rstrip('=')

print(f"URL: http://localhost:7889{path}?uid={uid}&expires={expires}&token={token}")
```

**访问文件：**
```bash
curl "http://localhost:7889/video/2024-01-01/movie/playlist.m3u8?uid=user123&expires=1234567890&token=xxx"
```

## 🔍 调试工具

### 浏览器检测
```bash
curl "http://localhost:7889/debug/browser?ua=Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"
```

### CIDR 测试
```bash
curl "http://localhost:7889/debug/cidr?ip=192.168.1.0/24&test_ip=192.168.1.100"
```

### IP 白名单调试
```bash
curl http://localhost:7889/debug/ip-whitelist
```

## ⚙️ 配置修改

编辑 `models/config.py`：

```python
# Redis 配置
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
REDIS_PASSWORD = "your_password"

# 后端服务器配置
BACKEND_HOST = "your-backend-server"
BACKEND_PORT = 27804

# 性能配置
HTTP_CONNECTOR_LIMIT = 100
STREAM_CHUNK_SIZE = 8192
```

## 🐛 故障排查

### 服务无法启动
1. 检查 Redis 是否运行
2. 检查依赖是否完整安装
3. 查看日志：`tail -f logs/proxy_fastapi.log`

### IP 白名单不工作
1. 使用 `/debug/ip-whitelist` 查看白名单
2. 使用 `/debug/cidr` 测试 CIDR 匹配
3. 检查 User-Agent 是否正确

### HMAC 验证失败
1. 确认 SECRET_KEY 配置正确
2. 检查时间戳是否在有效期内
3. 验证签名计算逻辑

## 📚 更多文档

- [完整文档](README.md)
- [架构设计](docs/ARCHITECTURE.md)
- [API 文档](docs/README_FASTAPI.md)
- [监控面板](docs/README_MONITOR.md)

## 💡 最佳实践

1. **生产环境**
   - 修改 SECRET_KEY
   - 启用 HTTPS
   - 配置防火墙
   - 定期监控性能

2. **性能优化**
   - 调整 worker 数量
   - 优化 Redis 配置
   - 使用 uvloop

3. **安全加固**
   - 修改 API Key
   - 限制 IP 访问
   - 启用访问日志

## 🎉 开始使用

现在你已经准备好使用 HLS 文件代理服务器了！

有问题？查看 [docs/](docs/) 目录中的详细文档。
