"""
流量收集器模块
1MB流量起步，5分钟上报一次，上报后清除数据
"""
import asyncio
import time
import json
import logging
import os
from typing import Dict, Optional, Set
from collections import defaultdict
from datetime import datetime


class TrafficCollector:
    """轻量级流量收集器 - 1MB起步，5分钟上报，上报后清除"""
    
    def __init__(self, redis_manager, http_client_manager, logger, 
                 report_url: str, api_key: str = None):
        self.redis_manager = redis_manager
        self.http_client_manager = http_client_manager
        self.logger = logger
        self.report_url = report_url
        self.api_key = api_key
        
        # 流量收集配置
        self.MIN_BYTES_THRESHOLD = 1024 * 1024  # 1MB起步门槛上报
        self.REPORT_INTERVAL = 300  # 300即 5分钟上报一次
        
        # Worker身份
        self.worker_id = f"worker_{os.getpid()}_{int(time.time())}"
        
        # 流量缓存 - 只记录超过1MB的UID
        self._qualified_traffic: Dict[str, Dict] = {}
        
        # 临时累积器 - 用于判断是否达到1MB门槛
        self._accumulator: Dict[str, int] = defaultdict(int)
        
        # 累积器时间戳（用于清理）
        self._accumulator_timestamps: Dict[str, float] = {}
        
        # 统计信息
        self._stats = {
            'total_recorded_uids': 0,
            'total_reports_sent': 0,
            'total_bytes_reported': 0,
            'current_qualified_uids': 0,
            'reports_failed': 0,
            'accumulator_cleanups': 0
        }
        
        # 任务控制
        self._report_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        # 清理计数器
        self._cleanup_counter = 0
    
    def record_traffic(self, uid: str, bytes_transferred: int, file_type: str = "default", 
                      client_ip: str = "unknown", session_id: str = None):
        """记录流量 - 只有超过1MB的UID才会被正式记录"""
        try:
            if not uid or bytes_transferred <= 0:
                return
            
            current_time = time.time()
            
            # 如果已经在正式记录中，直接累加
            if uid in self._qualified_traffic:
                traffic_data = self._qualified_traffic[uid]
                traffic_data['total_bytes'] += bytes_transferred
                traffic_data['request_count'] += 1
                traffic_data['last_activity'] = current_time
                
                # 文件类型统计
                if file_type not in traffic_data['file_types']:
                    traffic_data['file_types'][file_type] = 0
                traffic_data['file_types'][file_type] += bytes_transferred
                
                # 更新唯一值（限制集合大小）
                if len(traffic_data['unique_ips']) < 20:
                    traffic_data['unique_ips'].add(client_ip)
                if session_id and len(traffic_data['unique_sessions']) < 10:
                    traffic_data['unique_sessions'].add(session_id)
                
                return
            
            # 否则先累加到临时累积器
            self._accumulator[uid] += bytes_transferred
            
            # 记录首次见到的时间
            if uid not in self._accumulator_timestamps:
                self._accumulator_timestamps[uid] = current_time
            
            # 检查是否达到1MB门槛
            if self._accumulator[uid] >= self.MIN_BYTES_THRESHOLD:
                # 达到门槛，转移到正式记录
                self._qualified_traffic[uid] = {
                    'total_bytes': self._accumulator[uid],
                    'request_count': 1,  # 这次是首次正式记录
                    'file_types': {file_type: self._accumulator[uid]},
                    'unique_ips': {client_ip},
                    'unique_sessions': {session_id} if session_id else set(),
                    'start_time': self._accumulator_timestamps[uid],
                    'last_activity': current_time
                }
                
                # 从累积器中清除
                del self._accumulator[uid]
                del self._accumulator_timestamps[uid]
                
                self._stats['total_recorded_uids'] += 1
                self.logger.info(f"🎯 UID {uid} 达到1MB门槛，开始正式记录流量 (累积: {self._accumulator[uid] if uid in self._accumulator else 'N/A'} bytes)")
            
            # 定期清理累积器
            self._maybe_cleanup_accumulator()
            
        except Exception as e:
            self.logger.error(f"记录流量失败 uid={uid}: {str(e)}")
    
    def _maybe_cleanup_accumulator(self):
        """定期清理累积器中未达标的UID"""
        self._cleanup_counter += 1
        if self._cleanup_counter < 1000:  # 每1000次调用清理一次
            return
        
        self._cleanup_counter = 0
        
        try:
            current_time = time.time()
            expired_uids = []
            
            # 清理超过10分钟还未达到1MB的UID
            for uid, timestamp in list(self._accumulator_timestamps.items()):
                if current_time - timestamp > 600:  # 10分钟
                    expired_uids.append(uid)
            
            for uid in expired_uids:
                self._accumulator.pop(uid, None)
                self._accumulator_timestamps.pop(uid, None)
            
            if expired_uids:
                self._stats['accumulator_cleanups'] += 1
                self.logger.debug(f"清理了 {len(expired_uids)} 个未达标UID")
                
        except Exception as e:
            self.logger.error(f"清理累积器失败: {str(e)}")
    
    async def _send_traffic_report(self) -> bool:
        """发送流量上报"""
        try:
            if not self._qualified_traffic:
                self.logger.debug("没有符合条件的流量数据需要上报")
                return True
            
            # 准备上报数据
            current_time = int(time.time())
            report_data = {
                'timestamp': current_time,
                'worker_id': self.worker_id,
                'report_interval_seconds': self.REPORT_INTERVAL,
                'min_bytes_threshold': self.MIN_BYTES_THRESHOLD,
                'total_qualified_uids': len(self._qualified_traffic),
                'traffic_details': []
            }
            
            total_bytes_in_report = 0
            total_requests_in_report = 0
            
            # 构建每个UID的详细数据
            for uid, data in self._qualified_traffic.items():
                duration = max(1, int(data['last_activity'] - data['start_time']))
                
                uid_report = {
                    'uid': uid,
                    'total_bytes': data['total_bytes'],
                    'total_mb': round(data['total_bytes'] / (1024 * 1024), 2),
                    'request_count': data['request_count'],
                    'duration_seconds': duration,
                    'start_time': int(data['start_time']),
                    'last_activity': int(data['last_activity']),
                    'file_types': dict(data['file_types']),
                    'unique_ips': len(data['unique_ips']),
                    'unique_sessions': len(data['unique_sessions']),
                    'avg_bytes_per_request': int(data['total_bytes'] / max(data['request_count'], 1)),
                    'bytes_per_second': int(data['total_bytes'] / duration)
                }
                
                report_data['traffic_details'].append(uid_report)
                total_bytes_in_report += data['total_bytes']
                total_requests_in_report += data['request_count']
            
            # 添加汇总信息
            report_data['summary'] = {
                'total_bytes': total_bytes_in_report,
                'total_mb': round(total_bytes_in_report / (1024 * 1024), 2),
                'total_requests': total_requests_in_report,
                'avg_bytes_per_uid': int(total_bytes_in_report / len(self._qualified_traffic)),
                'report_generated_at': datetime.utcfromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S UTC')
            }
            
            # 发送HTTP请求
            client = await self.http_client_manager.get_client()
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': f'TrafficCollector/1.0 Worker-{self.worker_id}',
                'X-Report-Time': str(current_time)
            }
            
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            self.logger.debug(f"准备上报流量数据: {len(self._qualified_traffic)} 个UID, 总计 {total_bytes_in_report:,} bytes")
            
            response = await client.post(
                self.report_url,
                json=report_data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                response_text = response.text
                
                # 上报成功 - 清除所有数据
                reported_uids = len(self._qualified_traffic)
                self._qualified_traffic.clear()
                
                self._stats['total_reports_sent'] += 1
                self._stats['total_bytes_reported'] += total_bytes_in_report
                self._stats['current_qualified_uids'] = 0
                
                self.logger.info(f"✅ 流量上报成功: {reported_uids} 个UID, 总流量: {total_bytes_in_report:,} bytes ({total_bytes_in_report/(1024*1024):.1f}MB)")
                self.logger.debug(f"上报响应前100字符: {response_text[:100]}...")
                
                return True
            else:
                error_text = response.text
                self.logger.error(f"❌ 上报失败 HTTP {response.status_code}: {error_text[:200]}...")
                self._stats['reports_failed'] += 1
                return False
                    
        except Exception as e:
            self.logger.error(f"❌ 发送流量上报失败: {str(e)}")
            import traceback
            self.logger.debug(f"上报异常详情: {traceback.format_exc()}")
            self._stats['reports_failed'] += 1
            return False
    
    async def _report_loop(self):
        """上报循环任务"""
        self.logger.info(f"🔄 开始流量上报循环，间隔: {self.REPORT_INTERVAL}秒")
        
        while self._running:
            try:
                cycle_start = time.time()
                
                # 执行上报
                await self._send_traffic_report()
                
                # 计算等待时间
                elapsed = time.time() - cycle_start
                sleep_time = max(0, self.REPORT_INTERVAL - elapsed)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    self.logger.warning(f"⚠️ 上报周期超时: 耗时 {elapsed:.2f}s，超过间隔 {self.REPORT_INTERVAL}s")
                
            except asyncio.CancelledError:
                self.logger.info("📤 流量上报任务被取消")
                break
            except Exception as e:
                self.logger.error(f"❌ 上报循环错误: {str(e)}")
                await asyncio.sleep(60)  # 错误时等待1分钟再重试
    
    async def _cleanup_loop(self):
        """定期清理任务"""
        while self._running:
            try:
                await asyncio.sleep(300)  # 每5分钟清理一次
                
                if not self._running:
                    break
                
                # 执行清理
                current_time = time.time()
                expired_uids = []
                
                for uid, timestamp in list(self._accumulator_timestamps.items()):
                    if current_time - timestamp > 1800:  # 30分钟未达标则清理
                        expired_uids.append(uid)
                
                for uid in expired_uids:
                    self._accumulator.pop(uid, None)
                    self._accumulator_timestamps.pop(uid, None)
                
                if expired_uids:
                    self.logger.info(f"🧹 定期清理了 {len(expired_uids)} 个长期未达标的UID")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"定期清理任务错误: {str(e)}")
    
    async def start(self):
        """启动流量收集器"""
        if self._running:
            self.logger.warning("流量收集器已经在运行中")
            return
        
        self._running = True
        
        # 启动上报任务
        self._report_task = asyncio.create_task(self._report_loop())
        
        # 启动清理任务
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info(f"🚀 流量收集器启动成功")
        self.logger.info(f"📊 配置参数:")
        self.logger.info(f"   - Worker ID: {self.worker_id}")
        self.logger.info(f"   - 流量门槛: {self.MIN_BYTES_THRESHOLD/(1024*1024):.1f}MB")
        self.logger.info(f"   - 上报间隔: {self.REPORT_INTERVAL}秒")
        self.logger.info(f"   - 上报URL: {self.report_url}")
        self.logger.info(f"   - API密钥: {'已配置' if self.api_key else '未配置'}")
    
    async def stop(self):
        """停止收集器并发送最后的数据"""
        if not self._running:
            return
        
        self.logger.info("🛑 正在停止流量收集器...")
        self._running = False
        
        # 停止定时任务
        if self._report_task:
            self._report_task.cancel()
            try:
                await self._report_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 发送最后的数据
        if self._qualified_traffic:
            self.logger.info(f"📤 发送最后的流量数据: {len(self._qualified_traffic)} 个UID")
            await self._send_traffic_report()
        
        self.logger.info(f"🛑 流量收集器已停止")
        self.logger.info(f"📈 最终统计: 记录了 {self._stats['total_recorded_uids']} 个UID, 发送了 {self._stats['total_reports_sent']} 次报告")
    
    def get_current_status(self) -> Dict:
        """获取当前状态"""
        self._stats['current_qualified_uids'] = len(self._qualified_traffic)
        
        current_traffic_summary = None
        if self._qualified_traffic:
            total_bytes = sum(d['total_bytes'] for d in self._qualified_traffic.values())
            total_requests = sum(d['request_count'] for d in self._qualified_traffic.values())
            current_traffic_summary = {
                'total_bytes': total_bytes,
                'total_mb': round(total_bytes / (1024 * 1024), 2),
                'total_requests': total_requests,
                'avg_bytes_per_uid': int(total_bytes / len(self._qualified_traffic))
            }
        
        return {
            'worker_id': self.worker_id,
            'running': self._running,
            'config': {
                'min_threshold_mb': self.MIN_BYTES_THRESHOLD / (1024 * 1024),
                'report_interval_seconds': self.REPORT_INTERVAL,
                'report_url': self.report_url,
                'api_key_configured': bool(self.api_key)
            },
            'current_state': {
                'qualified_uids': len(self._qualified_traffic),
                'pending_accumulator_uids': len(self._accumulator),
                'next_report_in_seconds': self.REPORT_INTERVAL  # 近似值
            },
            'statistics': self._stats.copy(),
            'current_traffic_summary': current_traffic_summary
        }


# 辅助函数
async def init_traffic_collector(redis_manager, http_client_manager, logger, 
                               report_url: str, api_key: str = None) -> TrafficCollector:
    """初始化流量收集器"""
    collector = TrafficCollector(
        redis_manager=redis_manager,
        http_client_manager=http_client_manager,
        logger=logger,
        report_url=report_url,
        api_key=api_key
    )
    await collector.start()
    return collector