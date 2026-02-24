# HLS 文件代理服务器

高性能异步文件代理服务器，专门针对 HLS 流媒体（m3u8/ts）优化，基于 FastAPI 框架构建。

## 🚀 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行服务器
```bash
# 开发环境
python app.py

# 生产环境
gunicorn -c gunicorn_fastapi.conf.py app:app
```

### 访问监控面板
```
http://localhost:7889/monitor
```

## 📁 项目结构

```
Server/FileProxy/
├── app.py                    # 主应用入口
├── requirements.txt          # 项目依赖
├── gunicorn_fastapi.conf.py # 生产环境配置
│
├── models/                   # 数据模型
│   └── config.py             # 配置管理
│
├── services/                 # 服务层
│   ├── http_client.py        # HTTP/2 客户端服务
│   ├── redis_service.py      # Redis 服务
│   ├── stream_proxy.py       # 流式代理服务
│   ├── session_service.py    # 会话管理服务
│   └── auth_service.py       # 认证服务
│
├── routes/                   # 路由层
│   ├── monitoring.py         # 监控端点
│   ├── debug.py              # 调试端点
│   └── proxy.py              # 代理路由
│
├── utils/                    # 工具函数
│   ├── helpers.py            # 通用辅助函数
│   ├── cidr_matcher.py       # CIDR IP 匹配
│   └── browser_detector.py   # 浏览器检测
│
├── middleware/               # 中间件
├── static/                   # 静态资源
│   ├── monitor.html          # 监控面板
│   ├── css/
│   └── js/
│
├── docs/                     # 文档
│   ├── README_FASTAPI.md
│   ├── README_MONITOR.md
│   ├── ARCHITECTURE.md
│   └── MIGRATION_SUMMARY.md
│
├── tests/                    # 测试文件
└── backups/                  # 备份文件
```

## ✨ 核心特性

### 性能优化
- ⚡ **HTTP/2 支持** - 多路复用，40-60% 并发提升
- ⚡ **uvloop 事件循环** - 2-4x 异步 I/O 性能
- ⚡ **零拷贝流式传输** - 降低 20-30% 内存使用
- ⚡ **智能连接池** - 减少 30-50% 连接开销
- ⚡ **IPv4/IPv6 双栈** - 完全支持 IPv6 网络

### HLS 专项优化
- 🎬 M3U8 不缓存策略
- 🎬 TS 文件流式传输
- 🎬 背压控制
- 🎬 自动重连机制

### 安全功能
- 🔐 HMAC 签名验证
- 🔐 IP 白名单（支持 CIDR，IPv4/IPv6）
- 🔐 会话管理
- 🔐 浏览器自适应访问控制
- 🔐 可配置的完全放行文件扩展名（支持 .ts, .webp 等）

### 监控可视化
- 📊 实时系统状态
- 📊 Redis 性能指标
- 📊 活跃连接统计
- 📊 流量收集

## 🔧 API 端点

### 监控
- `GET /health` - 健康检查
- `GET /stats` - 性能统计
- `GET /monitor` - Web 监控面板
- `GET /traffic` - 流量统计

### 调试
- `GET /debug/browser` - 浏览器检测调试
- `GET /debug/cidr` - CIDR 匹配调试
- `GET /debug/ip-whitelist` - IP 白名单调试

### 管理
- `POST /api/whitelist` - 添加 IP 白名单

### 代理
- `GET /{path:path}` - 文件代理（支持 HMAC 验证）

## 📚 文档

详细文档请查看 `docs/` 目录：

- **[README_FASTAPI.md](docs/README_FASTAPI.md)** - FastAPI 使用指南和部署说明
- **[README_MONITOR.md](docs/README_MONITOR.md)** - 监控面板使用文档
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - 系统架构和数据流
- **[MIGRATION_SUMMARY.md](docs/MIGRATION_SUMMARY.md)** - 迁移总结和性能指标
- **[MULTI_UA_IP_PAIRS.md](docs/MULTI_UA_IP_PAIRS.md)** - 多UA+IP对管理和静态文件验证功能
- **[FULLY_ALLOWED_EXTENSIONS.md](docs/FULLY_ALLOWED_EXTENSIONS.md)** - 完全放行文件扩展名配置

## ⚙️ 配置

主要配置在 `models/config.py` 中：

```python
# Redis 配置
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379

# 性能配置
HTTP_CONNECTOR_LIMIT = 100
STREAM_CHUNK_SIZE = 8192

# 后端配置
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 27804

# 多UA+IP对管理
MAX_UA_IP_PAIRS_PER_UID = 5  # 单个UID下最大UA+IP组合数

# 静态文件验证
ENABLE_STATIC_FILE_IP_ONLY_CHECK = False  # 静态文件IP-only验证

# 完全放行的文件扩展名（跳过所有验证）
FULLY_ALLOWED_EXTENSIONS = ('.ts', '.webp', '.php')  # 配置需要完全放行的文件类型
```

## 🔍 故障排查

### 检查服务状态
```bash
curl http://localhost:7889/health
```

### 查看日志
```bash
tail -f logs/proxy_fastapi.log
```

### 测试浏览器检测
```bash
curl "http://localhost:7889/debug/browser?ua=Mozilla/5.0..."
```

## 📝 开发指南

### 添加新路由
在 `routes/` 目录下创建新文件，然后在 `app.py` 中注册。

### 添加新服务
在 `services/` 目录下创建新文件，实现业务逻辑。

### 运行测试
```bash
cd tests

# IPv6 支持测试
python test_ipv6_support.py
python test_ipv6_network_config.py
python test_ipv6_normalization.py
python test_js_whitelist_ipv6.py

# 其他测试
python test_*.py
```

## 🌐 IPv6 支持

FileProxy 完全支持 IPv6，包括：
- ✅ IPv6 地址验证和 CIDR 匹配
- ✅ IPv6 固定白名单
- ✅ IPv6 客户端 IP 自动提取和规范化
- ✅ IPv4/IPv6 双栈服务器绑定
- ✅ JS 白名单 API 完全支持 IPv6

详细信息请参阅：
- [IPv6 支持文档](docs/IPV6_SUPPORT.md)
- [IPv6 验证报告](docs/IPV6_VERIFICATION_REPORT.md)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

与主项目保持一致
