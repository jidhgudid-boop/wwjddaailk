"""
配置模型
所有应用配置集中管理
"""
import socket
import logging
from typing import Dict

try:
    from performance_optimizer import PerformanceOptimizer
    PERFORMANCE_OPTIMIZER_ENABLED = True
    UVLOOP_AVAILABLE = True
except ImportError:
    PERFORMANCE_OPTIMIZER_ENABLED = False
    UVLOOP_AVAILABLE = False


class Config:
    """应用配置类"""
    
    # 日志配置
    LOG_LEVEL = logging.INFO  # 日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 日志文件最大大小（字节），默认 10MB
    LOG_BACKUP_COUNT = 10  # 保留的日志备份文件数量
    
    # Redis 配置
    REDIS_HOST = "1Panel-redis-pEFy"
    REDIS_PORT = 6379
    REDIS_DB = 6
    REDIS_PASSWORD = "redis_BSRAkw"
    
    # 性能优化器配置
    if PERFORMANCE_OPTIMIZER_ENABLED:
        optimizer = PerformanceOptimizer()
        opt_config = optimizer.get_optimized_config()
        
        # 获取 HLS 优化配置（8秒分片，CRF 26）
        hls_config = optimizer.get_hls_optimized_config(segment_duration=8, crf_quality=26)
        
        REDIS_POOL_SIZE = opt_config['REDIS_POOL_SIZE']
        HTTP_CONNECTOR_LIMIT = opt_config['HTTP_CONNECTOR_LIMIT']
        HTTP_CONNECTOR_LIMIT_PER_HOST = opt_config['HTTP_CONNECTOR_LIMIT_PER_HOST']
        HTTP_KEEPALIVE_TIMEOUT = opt_config['HTTP_KEEPALIVE_TIMEOUT']
        HTTP_CONNECT_TIMEOUT = opt_config['HTTP_CONNECT_TIMEOUT']
        HTTP_TOTAL_TIMEOUT = opt_config['HTTP_TOTAL_TIMEOUT']
        HTTP_DNS_CACHE_TTL = opt_config['HTTP_DNS_CACHE_TTL']
        
        # 使用 HLS 优化的流式传输参数
        STREAM_CHUNK_SIZE = hls_config['STREAM_CHUNK_SIZE']  # 针对 8秒/CRF26 优化
        BUFFER_SIZE = hls_config['BUFFER_SIZE']
        
        # HLS 配置信息（用于日志和监控）
        HLS_SEGMENT_DURATION = hls_config['SEGMENT_DURATION']
        HLS_CRF_QUALITY = hls_config['CRF_QUALITY']
        HLS_ESTIMATED_SEGMENT_SIZE = hls_config['ESTIMATED_SEGMENT_SIZE']
    else:
        REDIS_POOL_SIZE = 100
        HTTP_CONNECTOR_LIMIT = 100
        HTTP_CONNECTOR_LIMIT_PER_HOST = 30
        HTTP_KEEPALIVE_TIMEOUT = 30
        HTTP_CONNECT_TIMEOUT = 8
        HTTP_TOTAL_TIMEOUT = 45
        HTTP_DNS_CACHE_TTL = 500
        STREAM_CHUNK_SIZE = 65536  # 64KB，适合 8秒 TS 分片
        BUFFER_SIZE = 256 * 1024  # 256KB
        
        # HLS 配置信息（默认值）
        HLS_SEGMENT_DURATION = 8
        HLS_CRF_QUALITY = 26
        HLS_ESTIMATED_SEGMENT_SIZE = 3 * 1024 * 1024  # 约 3MB
    
    # TTL 配置（秒）
    SESSION_TTL = 2 * 60 * 60  # 2小时
    M3U8_SINGLE_USE_TTL = 5 * 60  # 5分钟
    USER_SESSION_TTL = 4 * 60 * 60  # 4小时
    IP_ACCESS_TTL = 1 * 60 * 60  # 1小时
    TOKEN_EXTEND_TTL = 75 * 60  # 75分钟活跃延期
    
    # Token 防重放保护配置
    # 对于包含 token 参数的请求（如 /index.m3u8?uid=315&expires=xxx&token=xxx）
    # 使用 Redis 限制每个 token 的使用次数，防止重放攻击
    TOKEN_REPLAY_ENABLED = True  # 是否启用 token 防重放保护
    TOKEN_REPLAY_MAX_USES = 1  # 每个 token 最大使用次数，默认1次（单次使用）
    TOKEN_REPLAY_TTL = 9600  # token 记录在 Redis 中的 TTL（秒），默认10分钟
    
    # Key 文件动态保护配置
    # 对 .key 文件（HLS加密密钥）实现动态接口保护，防止重放攻击
    # 通过动态修改 m3u8 文件内容，在 key URI 中添加验证参数
    KEY_PROTECT_ENABLED = True  # 是否启用 .key 文件动态保护
    KEY_PROTECT_DYNAMIC_M3U8 = True  # 是否动态修改 m3u8 内容（在 key URI 中添加参数）
    KEY_PROTECT_MAX_USES = 1  # 每个 token 关联的 .key 文件最大访问次数，默认1次
    KEY_PROTECT_TTL = 9600  # key 保护记录的 TTL（秒），默认10分钟
    KEY_PROTECT_EXTENSIONS = ('.key', 'enc.key')  # 需要保护的密钥文件扩展名
    
    # M3U8 原始内容 Redis 缓存配置
    # 缓存原始 m3u8 文件内容，避免频繁磁盘 I/O 读取
    M3U8_CONTENT_CACHE_ENABLED = True  # 是否启用 m3u8 内容缓存
    M3U8_CONTENT_CACHE_TTL = 3600  # 缓存 TTL（秒），默认1小时
    
    # CIDR IP 配置
    MAX_PATHS_PER_CIDR = 3
    MAX_UA_IP_PAIRS_PER_UID = 5  # 单个UID下允许的最大UA+IP组合数，超出时FIFO替换
    
    # 静态文件IP验证配置
    ENABLE_STATIC_FILE_IP_ONLY_CHECK = True  # 是否对静态文件仅验证IP（跳过路径保护）
    STATIC_FILE_EXTENSIONS = (
        '.jpg', '.jpeg', '.png', '.gif', '.svg',  # 图片
        '.css', '.js',  # 样式和脚本
        '.woff', '.woff2', '.ttf', '.eot',  # 字体
        '.ico', '.txt',  # 其他静态资源
    )
    
    # 完全放行的文件扩展名配置（这些文件类型将完全跳过所有验证，直接放行）
    # 支持的格式: 元组，每个元素为小写字符串，以点开头，例如: ('.ts', '.webp', '.php')
    # 注意：每个元素后面都应该加逗号，避免Python字符串字面量自动连接导致的解析错误
    FULLY_ALLOWED_EXTENSIONS = (
        '.ts',    # HLS 视频分片
        '.svv',  # 预览图
    )
    
    # 向后兼容配置：当 ENABLE_STATIC_FILE_IP_ONLY_CHECK = False 时使用的跳过验证扩展名
    # 这是旧版本行为，包含所有静态文件扩展名
    LEGACY_SKIP_VALIDATION_EXTENSIONS = (
        '.webp', '.php', '.js', '.css', '.ico', '.txt',
        '.woff', '.woff2', '.ttf', '.png', '.jpg', '.jpeg', '.gif', '.svg',
    )
    
    # Safe Key Protect 配置
    SAFE_KEY_PROTECT_ENABLED = False
    SAFE_KEY_PROTECT_REDIRECT_BASE_URL = "https://v.yuelk.com/pyvideo2/keyroute/"
    
    # M3U8 访问控制配置
    M3U8_DEFAULT_MAX_ACCESS_COUNT = 1
    M3U8_ACCESS_LIMITS = {
        'mobile_browser': {
            'qq': 2, 'uc': 1, 'baidu': 1,
            'chrome_mobile': 1, 'safari_mobile': 1,
            'default': 1
        },
        'desktop_browser': {
            'chrome': 1, 'firefox': 1, 'edge': 1,
            'safari': 1, 'default': 1
        },
        'download_tool': {'default': 1},
        'unknown': {'default': 1}
    }
    
    M3U8_ACCESS_WINDOW_TTL = {
        'mobile_browser': 3 * 60,
        'desktop_browser': 2 * 60,
        'download_tool': 1 * 60,
        'unknown': 1 * 60
    }
    
    ENABLE_BROWSER_ADAPTIVE_ACCESS = True
    ENABLE_DETAILED_ACCESS_LOGGING = False
    
    # 缓存配置
    M3U8_CACHE_TTL = 0
    TS_CACHE_TTL = 5 * 60
    STATIC_CACHE_TTL = 60 * 60
    DEFAULT_CACHE_TTL = 10 * 60
    FORCE_NO_CACHE_M3U8 = True
    
    # Cookie 配置
    COOKIE_SECURE = False
    COOKIE_HTTPONLY = True
    COOKIE_SAMESITE = "Lax"
    
    # 流量收集器配置
    TRAFFIC_COLLECTOR_ENABLED = True
    TRAFFIC_REPORT_URL = "https://v.yuelk.com/pyvideo2/api/traffic/report"
    TRAFFIC_API_KEY = "RosZ7eXV8dpDuouXGfhWp9N6yre2DBBnbRMcruTXLGwSxwgGH98ihoNG"
    TRAFFIC_MIN_BYTES_THRESHOLD = 1024 * 1024
    TRAFFIC_REPORT_INTERVAL = 10
    
    # 安全配置
    SECRET_KEY = b"super_lrVgOlXDW8E1aj1eFfHVDHXu9XZBtYNE"
    API_KEY = "F2UkWEJZRBxC7"  # API 访问密钥（用于白名单和文件检查API）
    
    # JS白名单追踪功能配置
    ENABLE_JS_WHITELIST_TRACKER = True  # 是否启用JS白名单追踪功能
    JS_WHITELIST_TRACKER_TTL = 60 * 60  # JS访问追踪记录TTL（秒），默认60分钟
    JS_WHITELIST_SECRET_KEY = b"js_3ZOJaPycOs03LPpEIOhFAfW3FC4OJnLm"  # JS白名单HMAC签名密钥（用于前端签名认证）
    JS_WHITELIST_SIGNATURE_TTL = 60 * 60  # JS白名单签名有效期（秒），默认1小时
    
    # 固定白名单IP配置（这些IP会完全跳过所有验证，直接放行）
    # 支持单个IP和CIDR格式，例如: ["192.168.1.100", "10.0.0.0/24"]
    FIXED_IP_WHITELIST = ["43.161.234.19","43.161.228.132","38.207.168.207","67.230.173.230"]
    
    # 测试模式配置（用于开发和测试，生产环境应设为 False）
    DISABLE_IP_WHITELIST = False  # 设为 True 跳过 IP 白名单检查
    DISABLE_PATH_PROTECTION = False  # 设为 True 跳过路径保护检查
    DISABLE_SESSION_VALIDATION = False  # 设为 True 跳过会话验证
    
    # 调试模式配置（用于排查问题，生产环境应设为 False）
    # 注意：启用调试模式会输出大量日志，仅在排查问题时临时启用
    # 日志文件位于 logs/proxy_fastapi.log，自动轮转（最大10MB/文件，保留10个备份）
    DEBUG_MODE = True  # 设为 True 启用详细的调试日志
    DEBUG_FULLY_ALLOWED_EXTENSIONS = True  # 设为 True 启用 FULLY_ALLOWED_EXTENSIONS 的详细调试信息
    
    # CORS 配置
    CORS_ALLOW_ORIGINS = ["*"]
    CORS_ALLOW_CREDENTIALS = True
    CORS_ALLOW_METHODS = ["*"]
    CORS_ALLOW_HEADERS = ["*"]
    
    # Session 配置
    SESSION_COOKIE_NAME = "session_id_fileserver"
    
    # 后端配置
    # Backend mode: 'http' or 'filesystem'
    BACKEND_MODE = "filesystem"  # 可选: 'http' 或 'filesystem'
    
    # HTTP backend configuration (when BACKEND_MODE = 'http')
    BACKEND_HOST = "172.17.0.1"
    BACKEND_PORT = 443
    BACKEND_USE_HTTPS = True
    BACKEND_SSL_VERIFY = False
    PROXY_HOST_HEADER = "video-files.yuelk.com"
    
    # Filesystem backend configuration (when BACKEND_MODE = 'filesystem')
    BACKEND_FILESYSTEM_ROOT = "/data"  # 本地文件系统根目录
    BACKEND_FILESYSTEM_SENDFILE = True  # 启用 sendfile 零拷贝传输
    BACKEND_FILESYSTEM_BUFFER_SIZE = 64 * 1024  # 64KB buffer for filesystem reads
    
    # Nginx 风格性能优化参数
    # 参考 nginx 默认配置优化文件传输性能
    SENDFILE_MAX_CHUNK = 2 * 1024 * 1024  # 2MB - nginx sendfile_max_chunk
    
    # 文件传输策略阈值（简化配置，只需一个参数）
    # >= STREAMING_THRESHOLD: 使用 StreamingResponse（流式传输，支持大文件和进度显示）
    # < STREAMING_THRESHOLD: 使用 FileResponse（sendfile 零拷贝，性能最优）
    STREAMING_THRESHOLD = 1 * 1024 * 1024  # 1MB - 大于等于此大小使用流式传输
    
    OUTPUT_BUFFERS_SIZE = 32 * 1024  # 32KB - nginx output_buffers 大小
    OUTPUT_BUFFERS_COUNT = 4  # nginx output_buffers 数量
    
    # 错误处理配置
    ENABLE_ERROR_RECOVERY = True
    LOG_CLIENT_DISCONNECTS = False
    SUPPRESS_TRANSPORT_ERRORS = True
    
    # 性能优化开关
    ENABLE_REQUEST_DEDUPLICATION = True
    ENABLE_PARALLEL_VALIDATION = True
    ENABLE_REDIS_PIPELINE = True
    ENABLE_RESPONSE_STREAMING = True
    
    # GZip 压缩：禁用以确保 Content-Length 正确显示
    # 重要：GZip 中间件会使用 chunked 编码传输，这会移除 Content-Length 头
    # 导致浏览器无法显示文件大小和下载进度百分比
    # 对于文件代理服务器，必须禁用 GZip 以保证用户体验
    ENABLE_GZIP_COMPRESSION = False


# 全局配置实例
config = Config()
