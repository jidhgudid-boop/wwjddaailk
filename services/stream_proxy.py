"""
流式代理服务
专门为 HLS 流媒体（m3u8/ts）高并发优化
支持 HTTP 和本地文件系统两种后端模式
"""
import asyncio
import logging
import os
import time
import uuid
import aiofiles
from pathlib import Path
from typing import Dict, AsyncIterator, Optional, Tuple
from fastapi import Request
from fastapi.responses import StreamingResponse, Response, FileResponse
import httpx

from models.config import config
from utils.helpers import ErrorHandler

logger = logging.getLogger(__name__)

# 带宽计算常量
COMPLETED_TRANSFER_WINDOW_SECONDS = 2.0  # 已完成传输包含在带宽统计中的时间窗口
INITIAL_TRANSFER_WINDOW_SECONDS = 0.5    # 初始传输阶段的时间窗口


class StreamProxyService:
    """
    流式代理服务
    
    支持两种后端模式：
    1. HTTP 模式：通过 HTTP/HTTPS 代理到远程服务器
    2. Filesystem 模式：直接从本地文件系统读取（零拷贝，性能更优）
    
    针对 HLS 流媒体的优化：
    - 零拷贝流式传输
    - 背压控制
    - 自动断点续传
    - 连接复用
    """
    
    def __init__(self, http_client_service, traffic_collector=None):
        self.http_client_service = http_client_service
        self.traffic_collector = traffic_collector
        self.backend_mode = config.BACKEND_MODE
        self.filesystem_root = Path(config.BACKEND_FILESYSTEM_ROOT) if hasattr(config, 'BACKEND_FILESYSTEM_ROOT') else None
        
        # 实时传输追踪
        self.active_transfers = {}  # {transfer_id: transfer_info}
        
        # 验证文件系统模式配置
        if self.backend_mode == "filesystem":
            if not self.filesystem_root:
                raise ValueError("BACKEND_FILESYSTEM_ROOT must be set when BACKEND_MODE is 'filesystem'")
            if not self.filesystem_root.exists():
                logger.warning(f"Filesystem root does not exist: {self.filesystem_root}")
            else:
                logger.info(f"Filesystem backend mode enabled: root={self.filesystem_root}")
    
    def _parse_range_header(self, range_header: str, file_size: int) -> Optional[Tuple[int, int]]:
        """
        解析 HTTP Range 请求头
        
        Args:
            range_header: Range 请求头值，例如 "bytes=0-1023"
            file_size: 文件总大小
        
        Returns:
            Optional[Tuple[int, int]]: (start_byte, end_byte) 或 None if invalid
        """
        try:
            # 解析 "bytes=start-end" 格式
            if not range_header.startswith("bytes="):
                return None
            
            range_spec = range_header[6:]  # 去掉 "bytes=" 前缀
            
            # 支持多种格式：
            # "0-499" -> 0-499
            # "500-" -> 500 到文件末尾
            # "-500" -> 最后500字节
            if '-' not in range_spec:
                return None
            
            parts = range_spec.split('-', 1)
            start_str, end_str = parts[0].strip(), parts[1].strip()
            
            if start_str and end_str:
                # "0-499" 格式
                start = int(start_str)
                end = int(end_str)
            elif start_str and not end_str:
                # "500-" 格式
                start = int(start_str)
                end = file_size - 1
            elif not start_str and end_str:
                # "-500" 格式（最后500字节）
                suffix_length = int(end_str)
                start = max(0, file_size - suffix_length)
                end = file_size - 1
            else:
                return None
            
            # 验证范围
            if start < 0 or end >= file_size or start > end:
                return None
            
            return (start, end)
            
        except (ValueError, IndexError):
            return None
    
    async def stream_file_chunks(
        self,
        file_path: Path,
        request: Request,
        chunk_size: int,
        uid: str = None,
        session_id: str = None,
        file_type: str = "default",
        client_ip: str = "unknown",
        start_byte: int = 0,
        end_byte: int = None
    ) -> AsyncIterator[bytes]:
        """
        从本地文件系统流式读取文件
        
        Args:
            file_path: 文件路径
            request: FastAPI 请求对象
            chunk_size: 块大小
            uid: 用户ID
            session_id: 会话ID
            file_type: 文件类型
            client_ip: 客户端IP
            start_byte: 开始字节位置（用于断点续传）
            end_byte: 结束字节位置（用于断点续传）
        
        Yields:
            bytes: 数据块
        """
        bytes_transferred = 0
        transfer_id = str(uuid.uuid4())
        
        # 计算总传输大小
        total_size = end_byte - start_byte + 1 if end_byte is not None else None
        
        # 注册活动传输
        self.active_transfers[transfer_id] = {
            'file_path': str(file_path.name),
            'full_path': str(file_path),
            'uid': uid,
            'session_id': session_id,
            'client_ip': client_ip,
            'file_type': file_type,
            'start_byte': start_byte,
            'end_byte': end_byte,
            'total_size': total_size,
            'bytes_transferred': 0,
            'speed_bps': 0,  # 初始化速度为0
            'start_time': time.time(),
            'last_update': time.time(),
            'first_byte_time': None,
            'status': 'active',
            'speed_history': [],  # 用于平滑速度计算
            'last_bytes': 0,  # 上次记录的字节数
            'last_speed_update': time.time()  # 上次速度更新时间
        }
        
        try:
            async with aiofiles.open(file_path, mode='rb') as f:
                # 如果有起始位置，先移动文件指针
                if start_byte > 0:
                    await f.seek(start_byte)
                
                # 计算要读取的总字节数
                bytes_to_read = None
                if end_byte is not None:
                    bytes_to_read = end_byte - start_byte + 1
                
                while True:
                    # 检查客户端是否断开连接
                    if await request.is_disconnected():
                        self.active_transfers[transfer_id]['status'] = 'disconnected'
                        logger.debug(f"客户端断开连接，停止传输: 已传输 {bytes_transferred} 字节")
                        break
                    
                    # 确定本次读取的大小
                    read_size = chunk_size
                    if bytes_to_read is not None:
                        remaining = bytes_to_read - bytes_transferred
                        if remaining <= 0:
                            break
                        read_size = min(chunk_size, remaining)
                    
                    chunk = await f.read(read_size)
                    if not chunk:
                        break
                    
                    # 记录首字节延迟
                    if self.active_transfers[transfer_id]['first_byte_time'] is None:
                        self.active_transfers[transfer_id]['first_byte_time'] = time.time()
                    
                    yield chunk
                    bytes_transferred += len(chunk)
                    
                    # 更新传输进度
                    current_time = time.time()
                    self.active_transfers[transfer_id]['bytes_transferred'] = bytes_transferred
                    self.active_transfers[transfer_id]['last_update'] = current_time
                    
                    # 计算瞬时速度（使用移动平均平滑）
                    time_since_last = current_time - self.active_transfers[transfer_id]['last_speed_update']
                    if time_since_last >= 0.5:  # 每0.5秒更新一次速度
                        bytes_since_last = bytes_transferred - self.active_transfers[transfer_id]['last_bytes']
                        instant_speed = bytes_since_last / time_since_last if time_since_last > 0 else 0
                        
                        # 添加到速度历史（保持最近10个样本）
                        speed_history = self.active_transfers[transfer_id]['speed_history']
                        speed_history.append(instant_speed)
                        if len(speed_history) > 10:
                            speed_history.pop(0)
                        
                        # 计算平滑速度（移动平均）
                        self.active_transfers[transfer_id]['speed_bps'] = sum(speed_history) / len(speed_history)
                        self.active_transfers[transfer_id]['last_bytes'] = bytes_transferred
                        self.active_transfers[transfer_id]['last_speed_update'] = current_time
            
            # 标记传输完成
            self.active_transfers[transfer_id]['status'] = 'completed'
            
            # 记录流量
            if self.traffic_collector and uid and bytes_transferred > 0:
                self.traffic_collector.record_traffic(
                    uid=uid,
                    bytes_transferred=bytes_transferred,
                    file_type=file_type,
                    client_ip=client_ip,
                    session_id=session_id
                )
            
            logger.debug(
                f"文件系统流式传输完成: 文件={file_path.name}, "
                f"传输字节={bytes_transferred}, UID={uid}"
            )
            
        except FileNotFoundError:
            self.active_transfers[transfer_id]['status'] = 'error'
            self.active_transfers[transfer_id]['error'] = 'File not found'
            logger.warning(f"文件未找到: {file_path}")
            raise
        except PermissionError:
            self.active_transfers[transfer_id]['status'] = 'error'
            self.active_transfers[transfer_id]['error'] = 'Permission denied'
            logger.error(f"文件权限错误: {file_path}")
            raise
        except Exception as e:
            self.active_transfers[transfer_id]['status'] = 'error'
            self.active_transfers[transfer_id]['error'] = str(e)
            if ErrorHandler.is_client_disconnect_error(e):
                logger.debug(f"客户端断开: 已传输 {bytes_transferred} 字节")
            else:
                logger.error(f"文件流式传输错误: {str(e)}")
                raise
        finally:
            # 5秒后清理完成或错误的传输记录
            async def cleanup_transfer():
                try:
                    await asyncio.sleep(5)
                    if transfer_id in self.active_transfers:
                        del self.active_transfers[transfer_id]
                except Exception as e:
                    logger.error(f"清理传输记录失败: {transfer_id} - {str(e)}")
            
            asyncio.create_task(cleanup_transfer())
    
    async def stream_chunks(
        self,
        response: httpx.Response,
        request: Request,
        chunk_size: int,
        uid: str = None,
        session_id: str = None,
        file_type: str = "default",
        client_ip: str = "unknown"
    ) -> AsyncIterator[bytes]:
        """
        流式传输数据块
        
        Args:
            response: httpx 响应对象
            request: FastAPI 请求对象
            chunk_size: 块大小
            uid: 用户ID
            session_id: 会话ID
            file_type: 文件类型
            client_ip: 客户端IP
        
        Yields:
            bytes: 数据块
        """
        bytes_transferred = 0
        transfer_id = str(uuid.uuid4())
        
        # 获取文件总大小（如果可用）
        content_length = response.headers.get("content-length")
        total_size = None
        if content_length:
            try:
                total_size = int(content_length)
            except (ValueError, TypeError):
                logger.debug(f"Invalid content-length header: {content_length}")
        
        # 从响应URL提取文件名
        file_path = response.url.path.split('/')[-1] if response.url else "unknown"
        full_path = response.url.path if response.url else "unknown"
        
        # 注册活动传输
        self.active_transfers[transfer_id] = {
            'file_path': file_path,
            'full_path': full_path,
            'uid': uid,
            'session_id': session_id,
            'client_ip': client_ip,
            'file_type': file_type,
            'start_byte': 0,
            'end_byte': total_size - 1 if total_size else None,
            'total_size': total_size,
            'bytes_transferred': 0,
            'speed_bps': 0,  # 初始化速度为0
            'start_time': time.time(),
            'last_update': time.time(),
            'first_byte_time': None,
            'status': 'active',
            'speed_history': [],  # 用于平滑速度计算
            'last_bytes': 0,  # 上次记录的字节数
            'last_speed_update': time.time()  # 上次速度更新时间
        }
        
        try:
            async for chunk in response.aiter_bytes(chunk_size):
                # 检查客户端是否断开连接
                if await request.is_disconnected():
                    self.active_transfers[transfer_id]['status'] = 'disconnected'
                    logger.debug(f"客户端断开连接，停止传输: 已传输 {bytes_transferred} 字节")
                    break
                
                # 记录首字节延迟
                if self.active_transfers[transfer_id]['first_byte_time'] is None:
                    self.active_transfers[transfer_id]['first_byte_time'] = time.time()
                
                yield chunk
                bytes_transferred += len(chunk)
                
                # 更新传输进度
                current_time = time.time()
                self.active_transfers[transfer_id]['bytes_transferred'] = bytes_transferred
                self.active_transfers[transfer_id]['last_update'] = current_time
                
                # 计算瞬时速度（使用移动平均平滑）
                time_since_last = current_time - self.active_transfers[transfer_id]['last_speed_update']
                if time_since_last >= 0.5:  # 每0.5秒更新一次速度
                    bytes_since_last = bytes_transferred - self.active_transfers[transfer_id]['last_bytes']
                    instant_speed = bytes_since_last / time_since_last if time_since_last > 0 else 0
                    
                    # 添加到速度历史（保持最近10个样本，即5秒历史）
                    speed_history = self.active_transfers[transfer_id]['speed_history']
                    speed_history.append(instant_speed)
                    if len(speed_history) > 10:
                        speed_history.pop(0)
                    
                    # 计算平滑速度（移动平均）
                    self.active_transfers[transfer_id]['speed_bps'] = sum(speed_history) / len(speed_history)
                    self.active_transfers[transfer_id]['last_bytes'] = bytes_transferred
                    self.active_transfers[transfer_id]['last_speed_update'] = current_time
            
            # 标记传输完成
            self.active_transfers[transfer_id]['status'] = 'completed'
            
            # 记录流量
            if self.traffic_collector and uid and bytes_transferred > 0:
                self.traffic_collector.record_traffic(
                    uid=uid,
                    bytes_transferred=bytes_transferred,
                    file_type=file_type,
                    client_ip=client_ip,
                    session_id=session_id
                )
            
            logger.debug(
                f"流式传输完成: 文件类型={file_type}, "
                f"传输字节={bytes_transferred}, UID={uid}"
            )
            
        except Exception as e:
            self.active_transfers[transfer_id]['status'] = 'error'
            self.active_transfers[transfer_id]['error'] = str(e)
            if ErrorHandler.is_client_disconnect_error(e):
                logger.debug(f"客户端断开: 已传输 {bytes_transferred} 字节")
            else:
                logger.error(f"流式传输错误: {str(e)}")
                raise
        finally:
            # 5秒后清理完成或错误的传输记录
            async def cleanup_transfer():
                try:
                    await asyncio.sleep(5)
                    if transfer_id in self.active_transfers:
                        del self.active_transfers[transfer_id]
                except Exception as e:
                    logger.error(f"清理传输记录失败: {transfer_id} - {str(e)}")
            
            asyncio.create_task(cleanup_transfer())
    
    def get_active_transfers(self) -> Dict:
        """
        获取当前活动传输的统计信息
        
        Returns:
            Dict: 活动传输信息
        """
        current_time = time.time()
        
        # 清理超过30秒未更新的传输记录
        stale_transfers = [
            tid for tid, info in self.active_transfers.items()
            if current_time - info.get('last_update', 0) > 30
        ]
        for tid in stale_transfers:
            del self.active_transfers[tid]
        
        # 统计信息
        active_count = sum(1 for t in self.active_transfers.values() if t['status'] == 'active')
        completed_count = sum(1 for t in self.active_transfers.values() if t['status'] == 'completed')
        
        # 计算总传输速度 - 包括active和最近完成的传输
        # 对于完成的传输，如果在最近2秒内完成，也计入带宽统计
        total_speed = 0
        for t in self.active_transfers.values():
            if t['status'] == 'active':
                # 活跃传输：使用当前速度，如果速度为0则计算平均速度
                speed_bps = t.get('speed_bps', 0)
                if speed_bps == 0 and t['bytes_transferred'] > 0:
                    # 对于非常快的传输（<0.5秒），瞬时速度可能还未计算
                    # 使用平均速度以确保带宽显示
                    elapsed = current_time - t['start_time']
                    if elapsed > 0:
                        speed_bps = t['bytes_transferred'] / elapsed
                total_speed += speed_bps
            elif t['status'] == 'completed':
                # 已完成传输：如果在指定时间窗口内完成，使用平均速度
                elapsed = current_time - t['start_time']
                time_since_complete = current_time - t.get('last_update', t['start_time'])
                if time_since_complete < COMPLETED_TRANSFER_WINDOW_SECONDS and elapsed > 0:
                    # 使用整个传输期间的平均速度
                    avg_speed = t['bytes_transferred'] / elapsed
                    total_speed += avg_speed
        
        # 获取传输详情（最多20个活动传输）
        transfers_list = []
        for tid, info in list(self.active_transfers.items())[:20]:
            # 计算首字节延迟（毫秒）
            first_byte_latency_ms = None
            if info.get('first_byte_time'):
                first_byte_latency_ms = (info['first_byte_time'] - info['start_time']) * 1000
            
            # 计算速度 - 改进以显示所有传输的实际速度
            elapsed = current_time - info['start_time']
            speed_bps = info.get('speed_bps', 0)
            bytes_transferred = info['bytes_transferred']
            total_size = info.get('total_size', 0)
            
            # 如果传输已完成或处于初始阶段，使用平均速度
            if info['status'] == 'completed' or elapsed < INITIAL_TRANSFER_WINDOW_SECONDS:
                # 已完成或刚开始的传输，使用平均速度
                if elapsed > 0:
                    speed_bps = bytes_transferred / elapsed
            elif speed_bps == 0 and elapsed > 0:
                # 如果瞬时速度为0但有传输数据，计算平均速度
                speed_bps = bytes_transferred / elapsed
            elif (total_size and total_size < 1024 * 1024) or elapsed < 2.0:
                # 小文件（<1MB）或传输时间短（<2秒），使用平均速度以避免波动
                if elapsed > 0:
                    avg_speed = bytes_transferred / elapsed
                    # 使用平均速度和瞬时速度的较大值，以更好地反映实际传输
                    speed_bps = max(speed_bps, avg_speed)
            
            transfer_info = {
                'transfer_id': tid,
                'file_path': info['file_path'],
                'full_path': info.get('full_path', info['file_path']),
                'uid': info.get('uid'),
                'session_id': info.get('session_id'),
                'status': info['status'],
                'bytes_transferred': bytes_transferred,
                'total_size': total_size,
                'speed_bps': speed_bps,
                'elapsed': current_time - info['start_time'],
                'client_ip': info['client_ip'],
                'file_type': info['file_type'],
                'first_byte_latency_ms': first_byte_latency_ms
            }
            
            # 计算进度百分比
            if info.get('total_size') and info['total_size'] > 0:
                transfer_info['progress_percent'] = (info['bytes_transferred'] / info['total_size']) * 100
            
            transfers_list.append(transfer_info)
        
        return {
            'active_transfers': active_count,
            'completed_transfers': completed_count,
            'total_speed_bps': total_speed,
            'total_speed_mbps': (total_speed * 8) / (1024 * 1024),  # 转换为 Mbps (兆比特/秒)
            'transfers': transfers_list,
            'timestamp': current_time,
            'total_tracked_transfers': len(self.active_transfers)  # 总追踪的传输数（包括所有状态）
        }
    
    async def read_file_range(
        self,
        file_path: Path,
        start_byte: int = 0,
        end_byte: int = None
    ) -> bytes:
        """
        读取文件的指定范围到内存（用于中等大小文件）
        
        Args:
            file_path: 文件路径
            start_byte: 开始字节位置
            end_byte: 结束字节位置（None 表示到文件末尾）
        
        Returns:
            bytes: 文件内容
        """
        async with aiofiles.open(file_path, mode='rb') as f:
            if start_byte > 0:
                await f.seek(start_byte)
            
            if end_byte is not None:
                size_to_read = end_byte - start_byte + 1
                return await f.read(size_to_read)
            else:
                return await f.read()
    
    async def proxy_filesystem(
        self,
        file_path: str,
        request: Request,
        chunk_size: int = None,
        uid: str = None,
        session_id: str = None,
        file_type: str = "default",
        client_ip: str = "unknown"
    ) -> Response:
        """
        从本地文件系统提供文件服务
        支持 HTTP Range 请求（断点续传）
        
        Args:
            file_path: 相对文件路径（相对于 filesystem_root）
            request: FastAPI 请求对象
            chunk_size: 块大小（None 时使用 nginx 风格自适应）
            uid: 用户ID
            session_id: 会话ID
            file_type: 文件类型
            client_ip: 客户端IP
        
        Returns:
            Response: 文件响应
        """
        try:
            # 构建完整文件路径
            full_path = self.filesystem_root / file_path.lstrip('/')
            
            # 安全检查：确保路径在 root 目录内
            try:
                full_path = full_path.resolve()
                if not str(full_path).startswith(str(self.filesystem_root.resolve())):
                    logger.warning(f"路径遍历攻击尝试: {file_path}")
                    return Response(status_code=403, content="Access Denied: Path traversal detected")
            except Exception as e:
                logger.error(f"路径解析错误: {str(e)}")
                return Response(status_code=400, content="Bad Request: Invalid path")
            
            # 检查文件是否存在
            if not full_path.exists():
                logger.warning(f"文件未找到: {full_path}")
                return Response(status_code=404, content="File Not Found")
            
            # 检查是否为文件（不是目录）
            if not full_path.is_file():
                logger.warning(f"请求的路径不是文件: {full_path}")
                return Response(status_code=403, content="Access Denied: Not a file")
            
            # 检查客户端连接状态
            if await request.is_disconnected():
                logger.debug(f"客户端已断开，取消文件读取: {full_path}")
                return Response(status_code=499, content="Client Closed Request")
            
            # 获取文件信息
            file_stat = full_path.stat()
            file_size = file_stat.st_size
            
            # Nginx 风格自适应 chunk size
            # 参考 nginx sendfile_max_chunk 和 output_buffers
            if chunk_size is None:
                if file_size < 1 * 1024 * 1024:  # <1MB
                    chunk_size = config.OUTPUT_BUFFERS_SIZE  # 32KB
                elif file_size < 32 * 1024 * 1024:  # <32MB
                    chunk_size = 128 * 1024  # 128KB (HLS 优化)
                elif file_size < 256 * 1024 * 1024:  # <256MB
                    chunk_size = 512 * 1024  # 512KB
                else:  # >256MB
                    chunk_size = min(config.SENDFILE_MAX_CHUNK, 2 * 1024 * 1024)  # 2MB
            
            # 检查是否为 Range 请求
            range_header = request.headers.get("Range")
            is_range_request = range_header is not None
            start_byte = 0
            end_byte = file_size - 1
            status_code = 200
            
            if is_range_request:
                # 解析 Range 头
                range_result = self._parse_range_header(range_header, file_size)
                
                if range_result:
                    start_byte, end_byte = range_result
                    status_code = 206  # Partial Content
                    logger.debug(f"Range 请求: {full_path.name}, range={start_byte}-{end_byte}/{file_size}")
                else:
                    # Range 格式无效，返回 416 Range Not Satisfiable
                    logger.warning(f"无效的 Range 头: {range_header}")
                    return Response(
                        status_code=416,
                        headers={"Content-Range": f"bytes */{file_size}"},
                        content="Range Not Satisfiable"
                    )
            
            # 计算实际传输大小
            content_length = end_byte - start_byte + 1
            
            # 准备响应头
            headers = self._prepare_filesystem_headers(full_path, file_type, content_length)
            
            # 添加 Range 相关头
            if is_range_request and status_code == 206:
                headers["Content-Range"] = f"bytes {start_byte}-{end_byte}/{file_size}"
            
            # 确定 media type
            media_type = self._get_media_type(full_path)
            
            # 决定使用哪种响应方式 (Nginx 风格优化)
            # 参考 nginx 配置：
            # - 小文件 sendfile 零拷贝
            # - 中等文件直接响应（确保 Content-Length）
            # - 大文件流式传输（节省内存）
            
            # 简化的文件传输策略：只用一个阈值
            # < STREAMING_THRESHOLD: 使用 FileResponse (sendfile 零拷贝)
            # >= STREAMING_THRESHOLD: 使用 StreamingResponse (流式传输)
            # 可通过 config.STREAMING_THRESHOLD 配置阈值
            
            use_streaming = (
                is_range_request or  # Range 请求必须用流式
                file_size >= config.STREAMING_THRESHOLD
            )
            
            if not use_streaming and config.BACKEND_FILESYSTEM_SENDFILE:
                # 小文件且非 Range 请求，使用 FileResponse（sendfile 零拷贝，性能最优）
                # 记录流量（FileResponse 会一次性传输）
                if self.traffic_collector and uid and file_size > 0:
                    self.traffic_collector.record_traffic(
                        uid=uid,
                        bytes_transferred=file_size,
                        file_type=file_type,
                        client_ip=client_ip,
                        session_id=session_id
                    )
                
                logger.debug(f"使用 FileResponse (sendfile): {full_path.name}, size={file_size}")
                return FileResponse(
                    path=str(full_path),
                    media_type=media_type,
                    headers=headers
                )
            
            else:
                # 大文件或 Range 请求，使用流式传输
                logger.debug(
                    f"使用 StreamingResponse (流式): {full_path.name}, "
                    f"size={file_size}, range={start_byte}-{end_byte}, "
                    f"content_length={content_length}"
                )
                
                return StreamingResponse(
                    self.stream_file_chunks(
                        file_path=full_path,
                        request=request,
                        chunk_size=chunk_size,
                        uid=uid,
                        session_id=session_id,
                        file_type=file_type,
                        client_ip=client_ip,
                        start_byte=start_byte,
                        end_byte=end_byte
                    ),
                    status_code=status_code,
                    headers=headers,
                    media_type=media_type
                )
            
        except FileNotFoundError:
            logger.warning(f"文件未找到: {file_path}")
            return Response(status_code=404, content="File Not Found")
        
        except PermissionError:
            logger.error(f"文件权限错误: {file_path}")
            return Response(status_code=403, content="Access Denied: Permission denied")
        
        except Exception as e:
            if ErrorHandler.is_client_disconnect_error(e):
                logger.debug(f"客户端断开连接: {file_path}")
                return Response(status_code=499, content="Client Closed Request")
            else:
                logger.error(f"文件系统代理失败: {file_path} - {str(e)}")
                return Response(status_code=500, content=f"Internal Server Error: {str(e)}")
    
    async def proxy_stream(
        self,
        remote_url: str = None,
        file_path: str = None,
        headers: Dict[str, str] = None,
        request: Request = None,
        chunk_size: int = 8192,
        uid: str = None,
        session_id: str = None,
        file_type: str = "default",
        client_ip: str = "unknown"
    ) -> Response:
        """
        统一代理接口 - 支持 HTTP 和 Filesystem 两种模式
        
        Args:
            remote_url: 远程URL (HTTP模式)
            file_path: 文件路径 (Filesystem模式)
            headers: 请求头 (HTTP模式使用)
            request: FastAPI 请求对象
            chunk_size: 块大小
            uid: 用户ID
            session_id: 会话ID
            file_type: 文件类型
            client_ip: 客户端IP
        
        Returns:
            Response: 响应对象
        """
        # 根据后端模式选择处理方式
        if self.backend_mode == "filesystem":
            # 文件系统模式
            if not file_path:
                # 从 remote_url 提取路径（如果传入的是 URL）
                if remote_url:
                    from urllib.parse import urlparse
                    parsed = urlparse(remote_url)
                    file_path = parsed.path
                else:
                    return Response(status_code=400, content="Bad Request: file_path required")
            
            return await self.proxy_filesystem(
                file_path=file_path,
                request=request,
                chunk_size=chunk_size,
                uid=uid,
                session_id=session_id,
                file_type=file_type,
                client_ip=client_ip
            )
        
        elif self.backend_mode == "http":
            # HTTP 模式
            if not remote_url:
                return Response(status_code=400, content="Bad Request: remote_url required")
            
            return await self._proxy_http_stream(
                remote_url=remote_url,
                headers=headers or {},
                request=request,
                chunk_size=chunk_size,
                uid=uid,
                session_id=session_id,
                file_type=file_type,
                client_ip=client_ip
            )
        
        else:
            logger.error(f"不支持的后端模式: {self.backend_mode}")
            return Response(status_code=500, content="Internal Server Error: Invalid backend mode")
    
    async def _proxy_http_stream(
        self,
        remote_url: str,
        headers: Dict[str, str],
        request: Request,
        chunk_size: int = 8192,
        uid: str = None,
        session_id: str = None,
        file_type: str = "default",
        client_ip: str = "unknown"
    ) -> Response:
        """
        HTTP 代理流式响应（内部方法）
        
        Args:
            remote_url: 远程URL
            headers: 请求头
            request: FastAPI 请求对象
            chunk_size: 块大小
            uid: 用户ID
            session_id: 会话ID
            file_type: 文件类型
            client_ip: 客户端IP
        
        Returns:
            Response: 流式响应
        """
        try:
            client = await self.http_client_service.get_client()
            
            # 检查客户端连接状态
            if await request.is_disconnected():
                logger.debug(f"客户端已断开，取消代理请求: {remote_url}")
                return Response(status_code=499, content="Client Closed Request")
            
            # 发起异步请求 - 使用流式响应
            response = await client.get(
                remote_url,
                headers=headers,
                follow_redirects=True
            )
            
            # 检查响应状态
            if response.status_code >= 400:
                logger.warning(f"后端返回错误状态 {response.status_code}: {remote_url}")
                return Response(status_code=response.status_code)
            
            # 准备响应头
            proxy_headers = self._prepare_headers(response, file_type)
            
            # 返回流式响应
            return StreamingResponse(
                self.stream_chunks(
                    response=response,
                    request=request,
                    chunk_size=chunk_size,
                    uid=uid,
                    session_id=session_id,
                    file_type=file_type,
                    client_ip=client_ip
                ),
                status_code=response.status_code,
                headers=proxy_headers,
                media_type=response.headers.get("content-type", "application/octet-stream")
            )
            
        except asyncio.TimeoutError:
            logger.warning(f"请求超时: {remote_url}")
            return Response(status_code=504, content="Gateway Timeout")
        
        except httpx.ConnectError as e:
            logger.error(f"连接错误: {remote_url} - {str(e)}")
            return Response(status_code=502, content=f"Bad Gateway: {str(e)}")
        
        except Exception as e:
            if ErrorHandler.is_client_disconnect_error(e):
                logger.debug(f"客户端断开连接: {remote_url}")
                return Response(status_code=499, content="Client Closed Request")
            else:
                logger.error(f"代理请求失败: {remote_url} - {str(e)}")
                return Response(status_code=502, content=f"Proxy Failed: {str(e)}")
    
    def _get_media_type(self, file_path: Path) -> str:
        """
        根据文件扩展名获取 MIME 类型
        
        Args:
            file_path: 文件路径
        
        Returns:
            str: MIME 类型
        """
        import mimetypes
        
        suffix = file_path.suffix.lower()
        
        # 常见的 HLS 和视频格式
        media_types = {
            '.m3u8': 'application/vnd.apple.mpegurl',
            '.ts': 'video/mp2t',
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.mkv': 'video/x-matroska',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.flv': 'video/x-flv',
            '.wmv': 'video/x-ms-wmv',
            '.key': 'application/octet-stream',
        }
        
        if suffix in media_types:
            return media_types[suffix]
        
        # 使用 mimetypes 模块作为后备
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return mime_type or 'application/octet-stream'
    
    def _prepare_filesystem_headers(
        self,
        file_path: Path,
        file_type: str,
        content_length: int
    ) -> Dict[str, str]:
        """
        准备文件系统响应头
        
        Args:
            file_path: 文件路径
            file_type: 文件类型
            content_length: 内容长度（可能是部分内容）
        
        Returns:
            Dict[str, str]: 响应头字典
        """
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length)
        }
        
        # 根据文件类型设置缓存策略
        if file_type == "m3u8":
            # m3u8 文件不缓存
            headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            headers["Pragma"] = "no-cache"
            headers["Expires"] = "0"
        elif file_type == "ts":
            # ts 文件可以短时间缓存
            headers["Cache-Control"] = "public, max-age=300"
        elif file_type == "static":
            # 静态资源长时间缓存
            headers["Cache-Control"] = "public, max-age=3600"
        else:
            # 默认缓存策略
            headers["Cache-Control"] = "public, max-age=600"
        
        return headers
    
    def _prepare_headers(self, response: httpx.Response, file_type: str) -> Dict[str, str]:
        """
        准备响应头
        
        Args:
            response: httpx 响应对象
            file_type: 文件类型
        
        Returns:
            Dict[str, str]: 响应头字典
        """
        # 排除不需要的头
        excluded_headers = {
            "transfer-encoding",
            "content-encoding",
            # "content-length" - 保留以确保显示文件总大小
            "connection",
            "access-control-allow-origin",
            "access-control-allow-methods",
            "access-control-allow-headers",
            "access-control-allow-credentials",
            "access-control-max-age",
            "access-control-expose-headers"
        }
        
        proxy_headers = {
            k: v for k, v in response.headers.items()
            if k.lower() not in excluded_headers
        }
        
        # 添加 Accept-Ranges 支持断点续传
        if "accept-ranges" not in proxy_headers:
            proxy_headers["Accept-Ranges"] = "bytes"
        
        # 根据文件类型设置缓存策略
        if file_type == "m3u8":
            # m3u8 文件不缓存
            proxy_headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            proxy_headers["Pragma"] = "no-cache"
            proxy_headers["Expires"] = "0"
        elif file_type == "ts":
            # ts 文件可以短时间缓存
            proxy_headers["Cache-Control"] = "public, max-age=300"
        
        return proxy_headers


# 创建全局实例的工厂函数
def create_stream_proxy_service(http_client_service, traffic_collector=None):
    return StreamProxyService(http_client_service, traffic_collector)
