# HLS 文件代理服务器 (FastAPI 版本)

## 概述

这是一个专门为 HLS 流媒体（m3u8/ts 文件）优化的高性能文件代理服务器，采用 FastAPI 框架构建，具有完全异步架构和模块化设计。

## 🚀 主要特性

### 性能优化
- **完全异步架构**: 使用 FastAPI + httpx，支持高并发请求
- **HTTP/2 支持**: 多路复用，减少连接开销
- **零拷贝流式传输**: chunk-based streaming，内存效率高
- **连接池管理**: 智能连接复用和 keep-alive
- **uvloop 事件循环**: 显著提升异步 I/O 性能

### HLS 专用优化
- **M3U8 缓存策略**: 禁用 m3u8 缓存，确保实时性
- **TS 文件流式传输**: 优化的块大小和背压控制
- **智能重试机制**: 自动重连和错误恢复
- **并发控制**: 防止资源耗尽

### 监控和可视化
- **实时监控面板**: Web 界面显示系统状态
- **性能图表**: Redis 延迟、连接数趋势
- **详细统计**: 会话、用户、流量等指标

### 模块化架构
```
Server/FileProxy/
├── app.py                 # 主应用入口
├── models/                # 数据模型
│   └── config.py          # 配置管理
├── services/              # 业务逻辑服务
│   ├── http_client.py     # HTTP 客户端服务
│   ├── redis_service.py   # Redis 服务
│   └── stream_proxy.py    # 流式代理服务
├── routes/                # API 路由（待添加）
│   ├── proxy.py           # 代理路由
│   ├── monitoring.py      # 监控路由
│   └── debug.py           # 调试路由
├── utils/                 # 工具函数
│   ├── helpers.py         # 通用辅助函数
│   ├── cidr_matcher.py    # CIDR IP 匹配
│   └── browser_detector.py # 浏览器检测
├── middleware/            # 中间件（待添加）
└── static/                # 静态文件（监控面板）
    ├── monitor.html
    ├── css/
    └── js/
```

## 📦 安装

### 1. 安装依赖

```bash
cd Server/FileProxy
pip install -r requirements.txt
```

### 2. 配置

编辑 `models/config.py` 修改配置：

```python
# Redis 配置
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
REDIS_DB = 6
REDIS_PASSWORD = "your_password"

# 后端服务器配置
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 27804
BACKEND_USE_HTTPS = False

# 性能配置
HTTP_CONNECTOR_LIMIT = 100  # 总连接数
HTTP_CONNECTOR_LIMIT_PER_HOST = 30  # 每个主机连接数
STREAM_CHUNK_SIZE = 8192  # 流式传输块大小
```

## 🎯 运行

### 开发环境

```bash
# 直接运行
python app.py

# 或使用 uvicorn
uvicorn app:app --host 0.0.0.0 --port 7889 --reload
```

### 生产环境

使用 gunicorn + uvicorn workers:

```bash
gunicorn app:app \
    --bind 0.0.0.0:7889 \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 120 \
    --keep-alive 5 \
    --max-requests 1000 \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log
```

或使用配置文件：

```bash
gunicorn -c gunicorn_fastapi.conf.py app:app
```

## 📊 监控面板

访问 `http://your-server:7889/monitor` 查看实时监控面板

### 功能
- 系统健康状态
- Redis 性能指标
- 活跃连接统计
- 流量收集器状态
- 性能趋势图表

## 🔧 API 端点

### 健康检查
```
GET /health
```

返回系统状态和各服务健康信息。

### 性能统计
```
GET /stats
```

返回详细的性能统计数据。

### 监控面板
```
GET /monitor
```

Web 监控界面。

## ⚡ 性能优化建议

### 1. 系统调优

```bash
# 增加文件描述符限制
ulimit -n 65535

# 调整 TCP 设置
sysctl -w net.core.somaxconn=65535
sysctl -w net.ipv4.tcp_max_syn_backlog=8192
```

### 2. Redis 优化

```bash
# redis.conf
maxmemory-policy allkeys-lru
maxclients 10000
timeout 300
tcp-keepalive 60
```

### 3. Worker 数量

推荐 worker 数量 = (2 × CPU 核心数) + 1

```bash
# 例如：8核CPU
gunicorn -w 17 ...
```

## 🔍 监控指标

### 关键指标
- **Redis 延迟**: < 10ms 优秀，10-50ms 良好
- **HTTP 连接数**: 应低于配置的最大值
- **活跃会话数**: 监控会话泄漏
- **内存使用**: 监控内存泄漏

### 日志位置
- 应用日志: `logs/proxy_fastapi.log`
- 访问日志: `logs/access.log`
- 错误日志: `logs/error.log`

## 🐛 故障排查

### 高延迟问题
1. 检查 Redis 连接池配置
2. 检查后端服务器响应时间
3. 增加 HTTP 连接池大小
4. 检查网络质量

### 连接耗尽
1. 增加连接池大小
2. 减少 keep-alive 超时
3. 检查连接泄漏
4. 增加 worker 数量

### 内存占用高
1. 减少 chunk 大小
2. 检查会话清理机制
3. 优化 Redis 内存策略
4. 启用 GZip 压缩

## 📚 技术栈

- **Web 框架**: FastAPI 0.104+
- **ASGI 服务器**: Uvicorn (uvloop)
- **HTTP 客户端**: httpx (HTTP/2)
- **数据库**: Redis (异步)
- **监控**: Chart.js
- **日志**: Python logging

## 🔐 安全建议

1. 在生产环境启用 HTTPS
2. 配置防火墙规则
3. 定期更新依赖
4. 使用环境变量管理敏感配置
5. 启用访问日志审计

## 📝 待办事项

- [ ] 完成代理路由实现
- [ ] 添加认证中间件
- [ ] 实现 IP 白名单功能
- [ ] 添加 HMAC 签名验证
- [ ] 完善错误处理
- [ ] 添加单元测试
- [ ] 性能基准测试
- [ ] Docker 容器化

## 🤝 贡献

欢迎提交 Issue 和 Pull Request!

## 📄 许可证

与主项目保持一致
