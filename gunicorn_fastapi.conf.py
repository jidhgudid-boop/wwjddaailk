import multiprocessing
import os
import sys

# 导入日志配置
sys.path.insert(0, os.path.dirname(__file__))
from logging_config import logconfig_dict

# 确保日志目录存在
def ensure_log_dir():
    """确保日志目录存在"""
    log_dir = os.path.join(os.getcwd(), "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    return log_dir

# 在配置加载时创建日志目录
LOG_DIR = ensure_log_dir()

# 服务器绑定
bind = "[::]:7889"  # 双栈绑定 - 同时支持IPv4和IPv6，FastAPI 服务端口

# 工作进程数 - 从环境变量读取（由 run.sh 设置），否则使用动态计算
workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))

# 工作进程类型 - 使用 Uvicorn Worker
worker_class = "uvicorn.workers.UvicornWorker"

# 工作进程连接数
worker_connections = 1000

# 超时设置（优化）
timeout = 30  # 请求超时（秒）
keepalive = 65  # Keep-Alive 超时（秒，与 HTTP 标准一致）

# 最大请求数（防止内存泄漏）- 增加以提高性能
max_requests = 10000
max_requests_jitter = 1000

# 使用共享内存提升性能
worker_tmp_dir = "/dev/shm"

# backlog 队列大小（nginx 风格）
backlog = 2048

# ===== X-Forwarded-For 支持 =====
# 告诉 Uvicorn 信任来自代理的 X-Forwarded-For 头
# 这会使 Uvicorn 的 ProxyHeadersMiddleware 更新 ASGI scope 中的 client IP
# 访问日志中的 %(h)s 将显示真实客户端 IP 而不是代理 IP
# 
# 安全注意事项：
# - 使用 "*" 表示信任所有来源的 XFF 头（仅当服务运行在可信代理后时使用）
# - 如果服务直接暴露在公网，应设置为具体的代理 IP 列表
# - 例如：forwarded_allow_ips = "127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
forwarded_allow_ips = "*"

# 日志配置 - 使用 Python logging 配置实现日志轮转
# 不再直接指定 accesslog 和 errorlog，而是使用 logconfig_dict
# 这样可以使用 RotatingFileHandler 实现自动轮转：每8MB自动切割，最多保留10份
# logconfig_dict 从 logging_config.py 导入

loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 进程名称
proc_name = "hmac-proxy-fastapi"

# 预加载应用（提高性能）
preload_app = True

# 工作目录
chdir = os.getcwd()

# PID 文件 - 优先使用系统目录，否则使用程序目录下的 logs/
if os.path.exists("/var/run/fileproxy") and os.access("/var/run/fileproxy", os.W_OK):
    pidfile = "/var/run/fileproxy/gunicorn_fastapi.pid"
else:
    pidfile = os.path.join(LOG_DIR, "gunicorn_fastapi.pid")

# 优雅重启超时
graceful_timeout = 30

# Uvicorn 特定配置（通过环境变量传递）
raw_env = [
    "UVICORN_LOOP=uvloop",  # 使用 uvloop 事件循环
    "UVICORN_HTTP=httptools",  # 使用 httptools HTTP 解析器
]
