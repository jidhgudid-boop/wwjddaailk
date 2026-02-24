"""
Gunicorn 日志配置
使用 RotatingFileHandler 实现日志自动轮转
"""
import os
from logging.handlers import RotatingFileHandler

# 确保日志目录存在
def ensure_log_dir():
    """确保日志目录存在"""
    log_dir = os.path.join(os.getcwd(), "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    return log_dir

LOG_DIR = ensure_log_dir()

# 日志轮转配置
LOG_MAX_BYTES = 8 * 1024 * 1024  # 8MB
LOG_BACKUP_COUNT = 10  # 最多保留10个备份文件

# 优先使用系统日志目录，否则使用程序目录下的 logs/
if os.path.exists("/var/log/fileproxy") and os.access("/var/log/fileproxy", os.W_OK):
    ACCESS_LOG_PATH = "/var/log/fileproxy/access_fastapi.log"
    ERROR_LOG_PATH = "/var/log/fileproxy/error_fastapi.log"
else:
    ACCESS_LOG_PATH = os.path.join(LOG_DIR, "access_fastapi.log")
    ERROR_LOG_PATH = os.path.join(LOG_DIR, "error_fastapi.log")

# Gunicorn 日志配置字典
logconfig_dict = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'generic': {
            'format': '%(asctime)s [%(process)d] [%(levelname)s] %(message)s',
            'datefmt': '[%Y-%m-%d %H:%M:%S %z]',
            'class': 'logging.Formatter'
        },
        'access': {
            'format': '%(message)s',
            'class': 'logging.Formatter'
        }
    },
    'handlers': {
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'generic',
            'filename': ERROR_LOG_PATH,
            'maxBytes': LOG_MAX_BYTES,
            'backupCount': LOG_BACKUP_COUNT,
            'encoding': 'utf-8'
        },
        'access_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'access',
            'filename': ACCESS_LOG_PATH,
            'maxBytes': LOG_MAX_BYTES,
            'backupCount': LOG_BACKUP_COUNT,
            'encoding': 'utf-8'
        }
    },
    'loggers': {
        'gunicorn.error': {
            'level': 'INFO',
            'handlers': ['error_file'],
            'propagate': False,
            'qualname': 'gunicorn.error'
        },
        'gunicorn.access': {
            'level': 'INFO',
            'handlers': ['access_file'],
            'propagate': False,
            'qualname': 'gunicorn.access'
        }
    },
    'root': {
        'level': 'WARNING',
        'handlers': ['error_file']
    }
}
