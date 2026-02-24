"""
FastAPI 文件代理服务器主应用
专门针对 HLS 流媒体高并发优化

特性：
- 完全异步架构
- HTTP/2 支持
- 零拷贝流式传输
- 高性能连接池
- 智能缓存策略
- 实时监控面板
"""
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from logging.handlers import RotatingFileHandler

# 导入配置和服务
from models.config import config
from services.http_client import http_client_service
from services.redis_service import redis_service
from services.stream_proxy import create_stream_proxy_service

# 导入路由
from routes import monitoring, debug, proxy as proxy_routes, file_check

# 导入流量收集器
try:
    from traffic_collector import init_traffic_collector
    TRAFFIC_COLLECTOR_AVAILABLE = True
except ImportError:
    TRAFFIC_COLLECTOR_AVAILABLE = False


# === 日志配置 ===
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

# 从配置文件读取日志设置，避免硬编码
# 配置日志轮转：每个日志文件最大 10MB（可配置），保留最多 10 个备份文件（可配置）
logging.basicConfig(
    level=config.LOG_LEVEL,  # 从 config.py 读取日志级别
    format='%(asctime)s [%(levelname)s] [PID:%(process)d] %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            filename=os.path.join(log_dir, 'proxy_fastapi.log'),
            maxBytes=config.LOG_MAX_BYTES,  # 从 config.py 读取最大文件大小
            backupCount=config.LOG_BACKUP_COUNT,  # 从 config.py 读取备份文件数量
            encoding='utf-8'
        )
    ]
)

logger = logging.getLogger(__name__)

# 全局变量
traffic_collector = None
stream_proxy_service = None


# === 生命周期管理 ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    启动时初始化所有服务，关闭时清理资源
    """
    global traffic_collector, stream_proxy_service
    
    # 启动时初始化
    logger.info("🚀 启动 FastAPI 文件代理服务器...")
    
    try:
        # 1. 初始化 Redis
        await redis_service.initialize(config)
        logger.info("✅ Redis 服务已初始化")
        
        # 2. 初始化 HTTP 客户端
        await http_client_service.initialize(config)
        logger.info("✅ HTTP 客户端服务已初始化")
        
        # 3. 初始化流式代理服务
        stream_proxy_service = create_stream_proxy_service(http_client_service)
        logger.info("✅ 流式代理服务已初始化")
        
        # 设置全局服务实例
        proxy_routes.set_stream_proxy_service(stream_proxy_service)
        monitoring.set_stream_proxy_service(stream_proxy_service)
        
        # 4. 初始化流量收集器（如果启用）
        if config.TRAFFIC_COLLECTOR_ENABLED and TRAFFIC_COLLECTOR_AVAILABLE:
            try:
                traffic_collector = await init_traffic_collector(
                    redis_manager=redis_service,
                    http_client_manager=http_client_service,
                    logger=logger,
                    report_url=config.TRAFFIC_REPORT_URL,
                    api_key=config.TRAFFIC_API_KEY
                )
                stream_proxy_service.traffic_collector = traffic_collector
                monitoring.set_traffic_collector(traffic_collector)
                logger.info("✅ 流量收集器已初始化")
            except Exception as e:
                logger.warning(f"⚠️  流量收集器初始化失败: {str(e)}")
        
        logger.info(f"🎉 服务启动完成！")
        logger.info(f"📊 配置概况:")
        logger.info(f"   - Redis连接池: {config.REDIS_POOL_SIZE}")
        logger.info(f"   - HTTP连接数: {config.HTTP_CONNECTOR_LIMIT}")
        logger.info(f"   - HTTP/2: 启用")
        logger.info(f"   - 流式传输: 启用")
        logger.info(f"   - 块大小: {config.STREAM_CHUNK_SIZE} 字节")
        
        yield  # 应用运行期间
        
    finally:
        # 关闭时清理资源
        logger.info("🛑 关闭 FastAPI 文件代理服务器...")
        
        if traffic_collector:
            try:
                await traffic_collector.stop()
                logger.info("✅ 流量收集器已停止")
            except Exception as e:
                logger.error(f"❌ 停止流量收集器失败: {str(e)}")
        
        await http_client_service.close()
        logger.info("✅ HTTP 客户端服务已关闭")
        
        await redis_service.close()
        logger.info("✅ Redis 服务已关闭")
        
        logger.info("👋 服务已完全关闭")


# === 创建 FastAPI 应用 ===
app = FastAPI(
    title="HLS 文件代理服务器",
    description="高性能异步文件代理服务器，专门针对 HLS 流媒体优化",
    version="2.0.0",
    lifespan=lifespan
)


# === 配置中间件 ===

# 1. CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOW_ORIGINS,
    allow_credentials=config.CORS_ALLOW_CREDENTIALS,
    allow_methods=config.CORS_ALLOW_METHODS,
    allow_headers=config.CORS_ALLOW_HEADERS,
    expose_headers=["Content-Length", "Content-Range", "Accept-Ranges", "Content-Type"]
)

# 2. GZip 压缩中间件（如果启用）
# 注意：对于视频和大文件应禁用压缩，因为它们已经压缩过，且压缩会移除 Content-Length 导致无法显示下载进度
# GZip 中间件会使用 chunked 编码，这会阻止浏览器显示文件大小百分比
# 解决方案：仅对文本类型启用 GZip，或完全禁用
if config.ENABLE_GZIP_COMPRESSION:
    # 不推荐：GZip 会移除 Content-Length，导致无法显示下载进度
    # 如果必须启用，请确保只压缩文本文件（.html, .css, .js）
    # 对于文件代理服务器，建议禁用 GZip 以保证 Content-Length 显示
    pass  # 禁用 GZip 以确保 Content-Length 正确显示
    # app.add_middleware(GZipMiddleware, minimum_size=1000)

# 3. XFF (X-Forwarded-For) 日志中间件
# 
# 访问日志 IP 显示说明：
# - Gunicorn 的 forwarded_allow_ips 配置使 Uvicorn 能够从 XFF 头获取真实客户端 IP 用于访问日志
# - 这个中间件提供额外的功能：在应用层面也能正确获取真实客户端 IP
# - 两者配合使用确保无论是服务器日志还是应用日志都显示正确的客户端 IP
# 
# 安全注意事项：当前配置信任所有来源的 XFF 头
# 如果服务直接暴露在公网而非通过可信代理，应配置 trusted_proxies 参数
# 例如：app.add_middleware(XFFLoggingMiddleware, trusted_proxies=["10.0.0.0/8", "192.168.0.0/16"])
from middleware.xff_logging import XFFLoggingMiddleware
app.add_middleware(XFFLoggingMiddleware)

logger.info("✅ 中间件已配置（包括 XFF 日志修复）")


# === 挂载静态文件 ===
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"✅ 静态文件目录已挂载: {static_dir}")


# === 注册路由 ===
# 监控和调试路由
app.include_router(monitoring.router, tags=["监控"])
app.include_router(debug.router, tags=["调试"])

# 文件检查API路由
app.include_router(file_check.router, tags=["文件检查"])

# JS白名单追踪路由
from routes import js_whitelist
app.include_router(js_whitelist.router, tags=["JS白名单追踪"])

# 代理路由（必须最后注册，因为有catch-all路径）
app.include_router(proxy_routes.router, tags=["代理"])

# === 基础路由 ===
@app.get("/")
async def root():
    """根路径 - 重定向到监控面板"""
    return RedirectResponse(url="/monitor")


# === 主程序入口 ===
if __name__ == "__main__":
    import uvicorn
    
    # 使用 uvloop 提升性能（如果可用）
    try:
        import uvloop
        uvloop.install()
        logger.info("✅ uvloop 已启用")
    except ImportError:
        logger.info("⚠️  uvloop 不可用，使用默认事件循环")
    
    uvicorn.run(
        "app:app",
        host="::",  # 双栈绑定 - 同时支持IPv4和IPv6
        port=7889,
        log_level="info",
        access_log=True,
        use_colors=True,
        workers=1  # 开发环境使用单进程
    )
