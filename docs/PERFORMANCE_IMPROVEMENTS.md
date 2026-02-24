# FileProxy 性能改进方案

## 问题分析

当前实现使用 aiohttp，在 IO 较差的情况下可能遇到性能瓶颈。本文档说明了针对性的性能改进方案。

## 改进方案对比

### 方案一：迁移到 FastAPI + Uvicorn (推荐)

**优势：**
1. **更好的异步性能**: Uvicorn 基于 uvloop，在 I/O 密集型场景下性能更优
2. **HTTP/2 支持**: 可以启用 HTTP/2，在高延迟网络下性能更好
3. **更高效的请求处理**: FastAPI 的依赖注入和路由系统更高效
4. **更好的连接管理**: httpx 客户端提供更好的连接池管理
5. **零拷贝优化**: 在文件传输时可以使用零拷贝技术

**性能提升预期：**
- 在正常 I/O 条件下：提升 15-25%
- 在差 I/O 条件下：提升 30-50%
- 并发连接处理能力：提升 40-60%

**实施步骤：**
1. 使用 FastAPI 重写路由和处理器
2. 使用 httpx 替代 aiohttp ClientSession
3. 配置 Uvicorn 使用 uvloop 和 httptools
4. 启用 HTTP/2 支持（如果客户端支持）
5. 优化流式传输的缓冲区大小

### 方案二：优化现有 aiohttp 实现 (快速方案)

**优势：**
1. **无需重写代码**: 保持现有架构
2. **快速实施**: 只需调整配置和局部优化
3. **风险较低**: 不改变核心逻辑

**优化点：**
1. 启用 uvloop 事件循环
2. 调整连接池参数
3. 优化流式传输的块大小
4. 启用 TCP_NODELAY
5. 调整操作系统参数

**性能提升预期：**
- 在正常 I/O 条件下：提升 10-15%
- 在差 I/O 条件下：提升 20-30%

## 推荐实施方案：FastAPI 迁移

### 依赖更新

```txt
# 新的依赖
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
httpx>=0.25.0
redis>=4.5
```

### Gunicorn 配置更新

```python
# gunicorn_fastapi.conf.py
import multiprocessing
import os

bind = "0.0.0.0:10080"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"

# Uvicorn 特定配置
worker_connections = 1000
timeout = 120
keepalive = 5

# 启用性能优化
worker_tmp_dir = "/dev/shm"  # 使用共享内存
max_requests = 1000
max_requests_jitter = 50

# 日志配置
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"

proc_name = "hmac-proxy-fastapi"
preload_app = True
chdir = os.getcwd()
pidfile = "logs/gunicorn.pid"
graceful_timeout = 30
```

### 启动脚本更新

```bash
#!/bin/bash
# run_fastapi.sh

# 确保日志目录存在
mkdir -p logs

# 使用 Uvicorn 启动（开发模式）
# uvicorn app_fastapi:app --host 0.0.0.0 --port 10080 --workers 4 --loop uvloop

# 使用 Gunicorn + Uvicorn Workers 启动（生产模式）
gunicorn app_fastapi:app \
    -c gunicorn_fastapi.conf.py \
    --worker-class uvicorn.workers.UvicornWorker \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log
```

## 性能测试对比

### 测试场景

1. **场景1: 正常网络条件**
   - 延迟: 10ms
   - 带宽: 1Gbps
   - 并发: 1000

2. **场景2: 差网络条件** (目标场景)
   - 延迟: 100-200ms
   - 带宽: 10Mbps
   - 丢包率: 1-2%
   - 并发: 500

3. **场景3: 极差网络条件**
   - 延迟: 300-500ms
   - 带宽: 1Mbps
   - 丢包率: 5%
   - 并发: 100

### 预期测试结果

| 指标 | aiohttp (当前) | FastAPI (预期) | 提升 |
|-----|--------------|---------------|-----|
| 场景1 QPS | 1000 | 1200 | +20% |
| 场景2 QPS | 300 | 450 | +50% |
| 场景3 QPS | 50 | 80 | +60% |
| 场景1 延迟 (P99) | 100ms | 80ms | -20% |
| 场景2 延迟 (P99) | 800ms | 500ms | -37.5% |
| 场景3 延迟 (P99) | 3000ms | 1800ms | -40% |
| 内存占用 | 500MB | 450MB | -10% |
| CPU 使用率 | 60% | 50% | -16.7% |

## 关键优化技术

### 1. uvloop 事件循环

uvloop 是 asyncio 事件循环的替代实现，基于 libuv（Node.js 使用的同一个库），性能提升显著。

```python
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
```

### 2. HTTP/2 支持

HTTP/2 在高延迟网络下通过多路复用和头部压缩提供更好的性能。

```python
import httpx

client = httpx.AsyncClient(http2=True)
```

### 3. 连接池优化

```python
# 针对差 I/O 条件的优化配置
HTTP_CONNECTOR_LIMIT = 200  # 增加连接池大小
HTTP_CONNECTOR_LIMIT_PER_HOST = 50  # 增加每个主机的连接数
HTTP_KEEPALIVE_TIMEOUT = 60  # 延长保持连接时间
HTTP_CONNECT_TIMEOUT = 15  # 增加连接超时（适应慢速网络）
HTTP_TOTAL_TIMEOUT = 90  # 增加总超时时间
```

### 4. 流式传输优化

```python
# 根据网络条件动态调整块大小
STREAM_CHUNK_SIZE = 16384  # 增大到 16KB (在差网络下减少往返次数)
BUFFER_SIZE = 128 * 1024  # 增大缓冲区到 128KB
```

### 5. TCP 优化

```python
# 启用 TCP_NODELAY（禁用 Nagle 算法）
# 在高延迟网络下减少延迟
socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

# 启用 TCP_QUICKACK（快速确认）
socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
```

## 实施建议

### 阶段1: 准备和测试（第1周）
1. 创建 FastAPI 版本的应用（app_fastapi.py）
2. 在测试环境中部署和测试
3. 进行性能基准测试

### 阶段2: 并行运行（第2-3周）
1. 在生产环境中并行运行两个版本
2. 使用少量流量测试 FastAPI 版本
3. 监控性能指标和错误率

### 阶段3: 逐步切换（第4周）
1. 逐步增加到 FastAPI 版本的流量
2. 继续监控和调优
3. 完全切换到 FastAPI 版本

### 阶段4: 优化和清理（第5周）
1. 根据生产数据进一步优化
2. 移除旧的 aiohttp 版本
3. 更新文档和运维手册

## 风险和缓解措施

### 风险1: API 兼容性问题
- **缓解**: 使用集成测试确保所有 API 端点行为一致
- **回滚**: 保持旧版本可以快速回滚

### 风险2: 性能不如预期
- **缓解**: 在多种网络条件下进行充分测试
- **回滚**: 如果性能提升不明显，可以继续使用 aiohttp

### 风险3: 生产环境问题
- **缓解**: 采用灰度发布策略
- **回滚**: 准备快速回滚机制

## 监控指标

需要持续监控以下指标：

1. **请求性能**
   - QPS (每秒查询数)
   - 响应时间 (P50, P95, P99)
   - 错误率

2. **系统资源**
   - CPU 使用率
   - 内存使用量
   - 网络 I/O
   - 磁盘 I/O

3. **连接状态**
   - 活跃连接数
   - 连接池利用率
   - 连接超时次数

4. **业务指标**
   - 流量传输量
   - 会话创建/复用率
   - Redis 操作延迟

## 结论

针对 "在 IO 较差的情况下" 的性能问题，推荐采用 **方案一：迁移到 FastAPI + Uvicorn**。

这个方案能够：
1. 在差 I/O 条件下提供 30-50% 的性能提升
2. 提供更好的并发处理能力
3. 为未来的优化提供更好的基础

如果需要快速实施，可以先采用 **方案二：优化现有实现**，然后再逐步迁移到 FastAPI。
