import multiprocessing
import os

# 服务器绑定
bind = "0.0.0.0:10080"

# 工作进程数
workers = 4  # 或者使用 multiprocessing.cpu_count()

# 工作进程类型
worker_class = "aiohttp.worker.GunicornWebWorker"

# 工作进程连接数
worker_connections = 1000

# 超时设置
timeout = 120
keepalive = 5

# 最大请求数（防止内存泄漏）
max_requests = 1000
max_requests_jitter = 50

# 日志配置
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 进程名称
proc_name = "hmac-proxy"

# 用户和组（可选）
# user = "nobody"
# group = "nobody"

# 预加载应用（可选，提高性能）
preload_app = True

# 工作目录
chdir = os.getcwd()

# PID 文件
pidfile = "logs/gunicorn.pid"

# 优雅重启超时
graceful_timeout = 30

# 临时目录
tmp_upload_dir = None