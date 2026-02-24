# -*- coding: utf-8 -*-
"""
性能优化插件 - 针对差 I/O 条件的优化
可以直接集成到现有 app.py 中，无需重写整个应用
"""

import asyncio
import logging
import math

# 尝试导入 uvloop 以获得更好的性能
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    UVLOOP_AVAILABLE = True
    logging.info("✅ uvloop 已启用 - 预期性能提升 30-50%")
except ImportError:
    UVLOOP_AVAILABLE = False
    logging.warning("⚠️  uvloop 未安装 - 建议安装以获得更好的性能: pip install uvloop")


class PerformanceOptimizer:
    """
    性能优化器类
    提供针对差 I/O 条件的各种优化
    """
    
    @staticmethod
    def get_optimized_config():
        """
        返回针对差 I/O 条件优化的配置
        针对 8秒 TS 分片、FFmpeg CRF 26 画质优化
        典型场景：2-4MB/segment，需要快速流式传输
        """
        return {
            # HTTP 连接池优化 - 针对高延迟网络
            'HTTP_CONNECTOR_LIMIT': 200,  # 增加连接池大小
            'HTTP_CONNECTOR_LIMIT_PER_HOST': 50,  # 每个主机更多连接
            'HTTP_KEEPALIVE_TIMEOUT': 60,  # 延长保持连接时间
            'HTTP_CONNECT_TIMEOUT': 15,  # 增加连接超时（适应慢速网络）
            'HTTP_TOTAL_TIMEOUT': 90,  # 增加总超时时间
            'HTTP_DNS_CACHE_TTL': 600,  # 延长 DNS 缓存时间
            
            # 流式传输优化 - 针对 8秒 TS 分片（2-4MB）优化
            # CRF 26 画质下，8秒视频约 2-4MB
            # 使用 64KB chunk 可以在 30-60 次请求内完成一个 TS 分片
            # 在 1-2 Mbps 带宽下可以流畅播放
            'STREAM_CHUNK_SIZE': 65536,  # 64KB chunks（优化 TS 分片传输）
            'BUFFER_SIZE': 256 * 1024,  # 256KB buffer（可缓存多个 chunk）
            
            # Redis 连接池优化
            'REDIS_POOL_SIZE': 150,  # 增加 Redis 连接池
            'REDIS_SOCKET_KEEPALIVE': True,
            'REDIS_SOCKET_TIMEOUT': 10,  # 增加超时
            
            # 启用所有性能优化开关
            'ENABLE_REQUEST_DEDUPLICATION': True,
            'ENABLE_PARALLEL_VALIDATION': True,
            'ENABLE_REDIS_PIPELINE': True,
            'ENABLE_RESPONSE_STREAMING': True,
        }
    
    @staticmethod
    def get_hls_optimized_config(segment_duration=8, crf_quality=26):
        """
        返回针对 HLS 流媒体优化的配置
        
        Args:
            segment_duration: TS 分片时长（秒），默认 8 秒
            crf_quality: FFmpeg CRF 画质，默认 26
        
        Returns:
            dict: 优化配置
        """
        # 根据 CRF 和分片时长估算文件大小
        # CRF 26 @ 8秒 ≈ 2-4MB per segment (假设 1080p H.264)
        # CRF 23 @ 8秒 ≈ 4-6MB per segment
        # CRF 18 @ 8秒 ≈ 8-12MB per segment
        
        estimated_segment_size_mb = {
            18: segment_duration * 1.2,  # 高画质
            23: segment_duration * 0.6,  # 中等画质
            26: segment_duration * 0.4,  # 较低画质（推荐）
            28: segment_duration * 0.3,  # 低画质
        }.get(crf_quality, segment_duration * 0.5)
        
        estimated_segment_bytes = int(estimated_segment_size_mb * 1024 * 1024)
        
        # 优化块大小：目标是在合理次数内完成传输
        # 目标：20-40 次 chunk 传输完成一个 segment
        optimal_chunk_size = max(16384, min(131072, estimated_segment_bytes // 30))
        
        # 向上取整到 2 的幂次
        optimal_chunk_size = 2 ** math.ceil(math.log2(optimal_chunk_size))
        
        return {
            'STREAM_CHUNK_SIZE': optimal_chunk_size,
            'BUFFER_SIZE': optimal_chunk_size * 4,
            'ESTIMATED_SEGMENT_SIZE': estimated_segment_bytes,
            'SEGMENT_DURATION': segment_duration,
            'CRF_QUALITY': crf_quality,
            'RECOMMENDED_BITRATE_MBPS': estimated_segment_size_mb / segment_duration * 8,
        }
    
    @staticmethod
    def apply_tcp_optimizations(sock):
        """
        应用 TCP 级别的优化
        在差 I/O 条件下可以显著改善性能
        """
        import socket
        
        try:
            # 禁用 Nagle 算法 - 减少小数据包的延迟
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            # 启用 TCP 快速确认
            if hasattr(socket, 'TCP_QUICKACK'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
            
            # 设置 TCP 保持连接
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            
            # 设置发送和接收缓冲区大小
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 262144)  # 256KB
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)  # 256KB
            
            return True
        except Exception as e:
            logging.warning(f"应用 TCP 优化失败: {str(e)}")
            return False
    
    @staticmethod
    def get_adaptive_chunk_size(network_quality='poor'):
        """
        根据网络质量返回自适应的块大小
        
        Args:
            network_quality: 'good', 'medium', 'poor', 'very_poor'
        
        Returns:
            int: 推荐的块大小（字节）
        """
        chunk_sizes = {
            'good': 8192,      # 8KB  - 正常网络
            'medium': 16384,   # 16KB - 中等网络
            'poor': 32768,     # 32KB - 差网络（减少往返次数）
            'very_poor': 65536 # 64KB - 极差网络
        }
        return chunk_sizes.get(network_quality, 16384)
    
    @staticmethod
    def get_adaptive_timeout(network_quality='poor'):
        """
        根据网络质量返回自适应的超时设置
        
        Args:
            network_quality: 'good', 'medium', 'poor', 'very_poor'
        
        Returns:
            dict: 超时配置
        """
        timeout_configs = {
            'good': {
                'connect': 5,
                'read': 30,
                'total': 45
            },
            'medium': {
                'connect': 10,
                'read': 45,
                'total': 60
            },
            'poor': {
                'connect': 15,
                'read': 60,
                'total': 90
            },
            'very_poor': {
                'connect': 20,
                'read': 90,
                'total': 120
            }
        }
        return timeout_configs.get(network_quality, timeout_configs['poor'])
    
    @staticmethod
    def estimate_network_quality(response_time_ms):
        """
        根据响应时间估算网络质量
        
        Args:
            response_time_ms: 响应时间（毫秒）
        
        Returns:
            str: 网络质量评估 ('good', 'medium', 'poor', 'very_poor')
        """
        if response_time_ms < 50:
            return 'good'
        elif response_time_ms < 150:
            return 'medium'
        elif response_time_ms < 300:
            return 'poor'
        else:
            return 'very_poor'


class AdaptiveRateLimiter:
    """
    自适应速率限制器
    根据网络状况动态调整请求速率
    """
    
    def __init__(self, initial_rate=100):
        self.current_rate = initial_rate
        self.min_rate = 10
        self.max_rate = 1000
        self.error_count = 0
        self.success_count = 0
        self.check_interval = 100  # 每100个请求检查一次
    
    def on_success(self):
        """记录成功请求"""
        self.success_count += 1
        if self.success_count >= self.check_interval:
            self._adjust_rate()
    
    def on_error(self):
        """记录失败请求"""
        self.error_count += 1
        if self.error_count + self.success_count >= self.check_interval:
            self._adjust_rate()
    
    def _adjust_rate(self):
        """根据错误率调整速率"""
        total = self.success_count + self.error_count
        error_rate = self.error_count / total if total > 0 else 0
        
        if error_rate > 0.1:  # 错误率超过10%
            # 降低速率
            self.current_rate = max(self.min_rate, self.current_rate * 0.8)
            logging.warning(f"⬇️  降低请求速率到 {self.current_rate:.0f}/s (错误率: {error_rate:.1%})")
        elif error_rate < 0.02:  # 错误率低于2%
            # 提高速率
            self.current_rate = min(self.max_rate, self.current_rate * 1.2)
            logging.info(f"⬆️  提高请求速率到 {self.current_rate:.0f}/s (错误率: {error_rate:.1%})")
        
        # 重置计数器
        self.error_count = 0
        self.success_count = 0
    
    def get_current_rate(self):
        """获取当前速率"""
        return self.current_rate


# 性能统计
class PerformanceMetrics:
    """
    性能指标收集器
    """
    
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.total_bytes = 0
        self.total_time = 0.0
        self.response_times = []
        self.max_response_time = 0
        self.min_response_time = float('inf')
    
    def record_request(self, bytes_transferred, response_time, is_error=False):
        """记录请求指标"""
        self.request_count += 1
        if is_error:
            self.error_count += 1
        else:
            self.total_bytes += bytes_transferred
            self.total_time += response_time
            self.response_times.append(response_time)
            
            if response_time > self.max_response_time:
                self.max_response_time = response_time
            if response_time < self.min_response_time:
                self.min_response_time = response_time
            
            # 只保留最近1000个响应时间
            if len(self.response_times) > 1000:
                self.response_times = self.response_times[-1000:]
    
    def get_stats(self):
        """获取统计信息"""
        if self.request_count == 0:
            return {}
        
        avg_response_time = self.total_time / (self.request_count - self.error_count) if (self.request_count - self.error_count) > 0 else 0
        error_rate = self.error_count / self.request_count
        throughput_mbps = (self.total_bytes * 8) / (self.total_time * 1024 * 1024) if self.total_time > 0 else 0
        
        # 计算 P95 和 P99
        if self.response_times:
            sorted_times = sorted(self.response_times)
            p95_index = int(len(sorted_times) * 0.95)
            p99_index = int(len(sorted_times) * 0.99)
            p95 = sorted_times[p95_index] if p95_index < len(sorted_times) else 0
            p99 = sorted_times[p99_index] if p99_index < len(sorted_times) else 0
        else:
            p95 = p99 = 0
        
        return {
            'total_requests': self.request_count,
            'error_count': self.error_count,
            'error_rate': f"{error_rate:.2%}",
            'total_bytes_transferred': self.total_bytes,
            'avg_response_time_ms': f"{avg_response_time * 1000:.2f}",
            'min_response_time_ms': f"{self.min_response_time * 1000:.2f}",
            'max_response_time_ms': f"{self.max_response_time * 1000:.2f}",
            'p95_response_time_ms': f"{p95 * 1000:.2f}",
            'p99_response_time_ms': f"{p99 * 1000:.2f}",
            'throughput_mbps': f"{throughput_mbps:.2f}",
            'uvloop_enabled': UVLOOP_AVAILABLE
        }


# 全局性能指标实例
performance_metrics = PerformanceMetrics()
adaptive_rate_limiter = AdaptiveRateLimiter()


def get_performance_status():
    """获取性能状态报告"""
    return {
        'uvloop_enabled': UVLOOP_AVAILABLE,
        'metrics': performance_metrics.get_stats(),
        'current_rate_limit': adaptive_rate_limiter.get_current_rate(),
        'optimization_level': 'high' if UVLOOP_AVAILABLE else 'medium'
    }


if __name__ == '__main__':
    # 测试代码
    print("性能优化插件测试")
    print("=" * 50)
    
    optimizer = PerformanceOptimizer()
    
    print(f"\nuvloop 状态: {'✅ 已启用' if UVLOOP_AVAILABLE else '❌ 未启用'}")
    
    print("\n针对差 I/O 条件的优化配置:")
    config = optimizer.get_optimized_config()
    for key, value in config.items():
        print(f"  {key}: {value}")
    
    print("\n网络质量自适应配置:")
    for quality in ['good', 'medium', 'poor', 'very_poor']:
        chunk_size = optimizer.get_adaptive_chunk_size(quality)
        timeout = optimizer.get_adaptive_timeout(quality)
        print(f"  {quality}: chunk={chunk_size} bytes, timeout={timeout}")
    
    print("\n性能指标统计:")
    # 模拟一些请求
    for i in range(100):
        import random
        response_time = random.uniform(0.01, 0.5)
        bytes_transferred = random.randint(1024, 10240)
        is_error = random.random() < 0.05
        performance_metrics.record_request(bytes_transferred, response_time, is_error)
    
    stats = performance_metrics.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
