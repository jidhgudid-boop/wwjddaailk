"""
通用工具函数
"""
import re
import os
import hmac
import hashlib
import base64
import time
import ipaddress
from typing import Dict
from fastapi import Request


def get_client_ip(request: Request) -> str:
    """
    获取客户端真实IP并规范化（支持IPv4和IPv6）
    
    规范化说明:
    - IPv4: 保持原样
    - IPv6: 使用压缩格式 (如 2001:db8::1)
    - IPv4映射的IPv6: 保持IPv6格式 (如 ::ffff:192.0.2.1)
    
    这确保同一IP地址的不同表示形式产生相同的hash
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip_str = forwarded_for.split(',')[0].strip()
    elif (real_ip := request.headers.get("x-real-ip")):
        ip_str = real_ip.strip()
    elif request.client:
        ip_str = request.client.host
    else:
        return "unknown"
    
    # 规范化IP地址
    try:
        # 使用ipaddress模块规范化IP地址
        # IPv6会被转换为压缩格式，IPv4保持不变
        ip_obj = ipaddress.ip_address(ip_str)
        normalized_ip = str(ip_obj)
        return normalized_ip
    except ValueError:
        # 如果无法解析为有效IP，返回原值
        return ip_str


def extract_match_key(path: str) -> str:
    """提取路径中的匹配关键字"""
    try:
        path = path.rstrip('/')
        parts = path.split('/')
        
        # 查找日期模式 (YYYY-MM-DD)
        date_pattern = re.compile(r'\d{4}-\d{2}-\d{2}')
        date_index = -1
        for i, part in enumerate(parts):
            if date_pattern.match(part):
                date_index = i
                break
        
        # 如果找到日期，返回日期后的文件夹
        if date_index != -1 and date_index + 1 < len(parts):
            return parts[date_index + 1]
        
        # 否则返回文件名前的文件夹
        return os.path.basename(os.path.dirname(path))
    
    except Exception:
        return ""


def validate_api_key(authorization: str, expected_api_key: str) -> bool:
    """
    验证API Key，支持两种格式：
    1. Bearer <API_KEY> (标准格式)
    2. <API_KEY> (简化格式)
    
    Args:
        authorization: Authorization 头的值
        expected_api_key: 预期的 API Key
        
    Returns:
        bool: 验证是否通过
    """
    if not authorization:
        return False
    
    # 尝试标准Bearer格式
    if authorization.startswith("Bearer "):
        token = authorization[7:]  # 移除 "Bearer " 前缀
        return token == expected_api_key
    
    # 尝试简化格式（直接是API Key）
    return authorization == expected_api_key


def validate_token(uid: str, path: str, expires: str, token: str, secret_key: bytes) -> bool:
    """
    HMAC 签名校验
    支持两种签名格式：
    1. 十六进制 (hexdigest) - 推荐用于JS白名单
    2. Base64 URL-safe (原有格式) - 向后兼容
    """
    try:
        current_time = int(time.time())
        expire_time = int(expires)
        if current_time > expire_time:
            return False
        
        msg = f"{uid}:{path}:{expires}".encode()
        hmac_obj = hmac.new(secret_key, msg, hashlib.sha256)
        
        # 尝试十六进制格式（JS白名单推荐格式）
        expected_hex = hmac_obj.hexdigest()
        if hmac.compare_digest(expected_hex, token):
            return True
        
        # 尝试Base64格式（向后兼容）
        expected_b64 = base64.urlsafe_b64encode(hmac_obj.digest()).decode().rstrip('=')
        return hmac.compare_digest(expected_b64, token)
    except (ValueError, TypeError):
        return False


def get_cache_headers(path: str, file_type: str) -> Dict[str, str]:
    """根据文件类型返回相应的缓存头"""
    # 可以根据需要实现缓存策略
    return {}


def create_session_cookie(session_id: str, session_ttl: int, cookie_config: Dict) -> str:
    """创建session cookie字符串"""
    cookie_parts = [
        f"{cookie_config['name']}={session_id}",
        "Path=/",
        f"Max-Age={session_ttl}"
    ]
    
    if cookie_config.get('httponly'):
        cookie_parts.append("HttpOnly")
    
    if cookie_config.get('secure'):
        cookie_parts.append("Secure")
    
    if cookie_config.get('samesite'):
        cookie_parts.append(f"SameSite={cookie_config['samesite']}")
    
    return "; ".join(cookie_parts)


class ErrorHandler:
    """错误处理器，用于分类和处理不同类型的异常"""
    
    @staticmethod
    def is_client_disconnect_error(exception) -> bool:
        """判断是否为客户端断开连接错误"""
        error_types = (
            'ClientConnectionResetError',
            'ConnectionResetError', 
            'BrokenPipeError',
            'ClientOSError',
            'ClientConnectorError',
            'RemoteProtocolError',
            'ConnectError'
        )
        error_messages = (
            'Cannot write to closing transport',
            'Connection reset by peer',
            'Broken pipe',
            'Transport is closing',
            'Connection lost',
            'Remote end closed connection'
        )
        
        exception_name = type(exception).__name__
        exception_str = str(exception).lower()
        
        return (exception_name in error_types or 
                any(msg.lower() in exception_str for msg in error_messages))
    
    @staticmethod
    def should_suppress_logging(exception) -> bool:
        """判断是否应该抑制日志记录"""
        return ErrorHandler.is_client_disconnect_error(exception)
