# FastAPI 文件代理服务器部署指南

本指南详细说明如何在 Debian/Ubuntu 系统上部署 FastAPI 文件代理服务器。

## 目录

- [系统要求](#系统要求)
- [自动部署（推荐）](#自动部署推荐)
- [手动部署](#手动部署)
- [Systemd 服务配置](#systemd-服务配置)
- [性能调优](#性能调优)
- [故障排查](#故障排查)

---

## 系统要求

### 操作系统
- **Ubuntu**: 20.04 LTS、22.04 LTS、24.04 LTS
- **Debian**: 10 (Buster)、11 (Bullseye)、12 (Bookworm)

### 硬件要求
- **CPU**: 2核心或以上（推荐 4核心）
- **内存**: 2GB 或以上（推荐 4GB）
- **磁盘**: 10GB 可用空间

### 软件依赖
- Python 3.8 或更高版本
- Redis 服务器（用于会话管理和缓存）
- 编译工具链（用于编译 uvloop）

---

## 自动部署（推荐）

使用 `run.sh` 脚本可以自动完成所有部署步骤。

### 1. 下载项目

```bash
cd /opt
sudo git clone <repository-url> fileproxy
cd fileproxy/Server/FileProxy
```

### 2. 运行部署脚本

```bash
chmod +x run.sh
./run.sh
```

### 脚本功能

`run.sh` 会自动执行以下操作：

1. ✅ 检测操作系统（Ubuntu/Debian）
2. ✅ 安装系统依赖包
   - Python 3、pip、venv
   - 编译工具（build-essential、python3-dev）
   - Redis 服务器
   - lsof、curl 等工具
3. ✅ 检查 Python 版本（需要 3.8+）
4. ✅ 创建和激活虚拟环境
5. ✅ 安装 Python 依赖包
6. ✅ 验证关键包安装（fastapi、uvicorn、httpx、redis、uvloop）
7. ✅ 检查端口占用（默认 7889）
8. ✅ 启动 FastAPI 服务器

### 配置选项

在 `run.sh` 顶部可以修改以下配置：

```bash
PORT=7889              # 服务端口
WORKER_COUNT=$(nproc)  # Worker 数量（默认=CPU核数）
```

---

## 手动部署

如果需要更细粒度的控制，可以手动执行部署步骤。

### 1. 安装系统依赖

```bash
sudo apt-get update
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    redis-server \
    lsof \
    curl
```

### 2. 启动 Redis

```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### 3. 创建虚拟环境

```bash
cd /opt/fileproxy/Server/FileProxy
python3 -m venv venv
source venv/bin/activate
```

### 4. 安装 Python 依赖

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### 5. 验证安装

```bash
python -c "import fastapi, uvicorn, httpx, redis, uvloop; print('✓ All packages installed')"
```

### 6. 启动服务（开发模式）

```bash
uvicorn app:app --host 0.0.0.0 --port 7889 --reload
```

### 7. 启动服务（生产模式）

```bash
gunicorn -c gunicorn_fastapi.conf.py app:app
```

---

## Systemd 服务配置

生产环境建议使用 systemd 服务进行管理。

### 1. 准备目录和权限

```bash
# 创建应用目录
sudo mkdir -p /opt/fileproxy

# 创建日志目录
sudo mkdir -p /var/log/fileproxy
sudo mkdir -p /var/run/fileproxy

# 设置权限
sudo useradd -r -s /bin/false www-data 2>/dev/null || true
sudo chown -R www-data:www-data /opt/fileproxy
sudo chown -R www-data:www-data /var/log/fileproxy
sudo chown -R www-data:www-data /var/run/fileproxy
```

### 2. 复制服务文件

```bash
sudo cp fileproxy.service /etc/systemd/system/
```

### 3. 修改服务配置（如需要）

编辑 `/etc/systemd/system/fileproxy.service`：

```ini
[Service]
# 修改用户（如果不使用 www-data）
User=your-user
Group=your-group

# 修改工作目录（如果不在 /opt/fileproxy）
WorkingDirectory=/your/custom/path
```

### 4. 启动服务

```bash
# 重载 systemd 配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start fileproxy

# 设置开机自启
sudo systemctl enable fileproxy

# 查看状态
sudo systemctl status fileproxy
```

### 5. 管理服务

```bash
# 停止服务
sudo systemctl stop fileproxy

# 重启服务
sudo systemctl restart fileproxy

# 重新加载配置（无缝重启）
sudo systemctl reload fileproxy

# 查看日志
sudo journalctl -u fileproxy -f
```

---

## 性能调优

### 1. Worker 数量

在 `gunicorn_fastapi.conf.py` 中调整：

```python
# CPU 密集型应用
workers = multiprocessing.cpu_count()

# I/O 密集型应用（推荐）
workers = multiprocessing.cpu_count() * 2 + 1
```

### 2. Redis 优化

编辑 `/etc/redis/redis.conf`：

```conf
# 最大内存
maxmemory 2gb

# 内存淘汰策略
maxmemory-policy allkeys-lru

# 持久化（根据需求）
save ""  # 禁用 RDB
appendonly no  # 禁用 AOF（缓存场景）
```

### 3. 系统参数

编辑 `/etc/sysctl.conf`：

```conf
# TCP 优化
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.ip_local_port_range = 10000 65535

# 文件句柄
fs.file-max = 2097152
```

应用配置：

```bash
sudo sysctl -p
```

### 4. Nginx 反向代理（可选）

```nginx
upstream fileproxy {
    server 127.0.0.1:7889;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://fileproxy;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 流式传输优化
        proxy_buffering off;
        proxy_request_buffering off;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
```

---

## 故障排查

### 问题 1：端口被占用

**症状**：`Address already in use`

**解决方案**：

```bash
# 查找占用端口的进程
sudo lsof -i :7889

# 杀死进程
sudo kill -9 <PID>

# 或使用 run.sh 自动处理
./run.sh
```

### 问题 2：Redis 连接失败

**症状**：`Connection refused` 或 `Could not connect to Redis`

**解决方案**：

```bash
# 检查 Redis 状态
sudo systemctl status redis-server

# 启动 Redis
sudo systemctl start redis-server

# 检查 Redis 连接
redis-cli ping  # 应该返回 PONG
```

### 问题 3：uvloop 编译失败

**症状**：`error: command 'gcc' failed` 或编译错误

**解决方案**：

```bash
# 安装编译依赖
sudo apt-get install -y build-essential python3-dev

# 重新安装
pip install --upgrade --force-reinstall uvloop
```

### 问题 4：权限错误

**症状**：`Permission denied` 或无法写入日志

**解决方案**：

```bash
# 设置正确的权限
sudo chown -R www-data:www-data /opt/fileproxy
sudo chown -R www-data:www-data /var/log/fileproxy

# 或使用当前用户
sudo chown -R $USER:$USER /opt/fileproxy
```

### 问题 5：内存不足

**症状**：服务器频繁重启或 OOM

**解决方案**：

```python
# 在 gunicorn_fastapi.conf.py 中减少 workers
workers = 2  # 降低 worker 数量

# 或增加系统内存
# 或优化 Redis 配置，限制内存使用
```

### 查看日志

```bash
# 应用日志
tail -f /var/log/fileproxy/error_fastapi.log
tail -f /var/log/fileproxy/access_fastapi.log

# Systemd 日志
sudo journalctl -u fileproxy -f

# 本地日志
tail -f logs/error_fastapi.log
```

---

## 健康检查

部署完成后，验证服务运行：

```bash
# 基本健康检查
curl http://localhost:7889/health

# 查看性能统计
curl http://localhost:7889/stats

# 访问监控面板
open http://localhost:7889/monitor
```

预期返回：

```json
{
    "status": "healthy",
    "timestamp": "2025-10-31T07:00:00",
    "version": "2.0.0",
    "redis": {
        "status": "connected",
        "ping": "ok"
    },
    "http_client": {
        "status": "ready"
    }
}
```

---

## 更新部署

```bash
# 1. 拉取最新代码
cd /opt/fileproxy
sudo -u www-data git pull

# 2. 激活虚拟环境
source venv/bin/activate

# 3. 更新依赖
pip install -r requirements.txt --upgrade

# 4. 重启服务
sudo systemctl restart fileproxy

# 5. 验证
curl http://localhost:7889/health
```

---

## 安全建议

1. **防火墙配置**：
   ```bash
   sudo ufw allow 7889/tcp
   sudo ufw enable
   ```

2. **HTTPS 配置**：使用 Nginx 反向代理配置 SSL/TLS

3. **限制访问**：配置 IP 白名单（见 `models/config.py`）

4. **日志轮转**：
   ```bash
   sudo nano /etc/logrotate.d/fileproxy
   ```
   
   内容：
   ```
   /var/log/fileproxy/*.log {
       daily
       rotate 7
       compress
       delaycompress
       notifempty
       create 0640 www-data www-data
       sharedscripts
       postrotate
           systemctl reload fileproxy > /dev/null 2>&1 || true
       endscript
   }
   ```

---

## 支持

- 查看完整文档：`docs/README_FASTAPI.md`
- 快速开始：`docs/QUICK_START.md`
- 架构设计：`docs/ARCHITECTURE.md`
- 故障排查：本文档

---

**部署完成后，服务将在 `http://0.0.0.0:7889` 上运行！**
