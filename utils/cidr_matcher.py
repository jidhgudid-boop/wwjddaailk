"""
工具类 - CIDR IP 匹配
"""
import ipaddress
from typing import List, Tuple


class CIDRMatcher:
    """CIDR IP匹配工具类，支持IPv4 CIDR表示法"""
    
    @staticmethod
    def is_cidr_notation(ip_or_cidr: str) -> bool:
        """检查字符串是否为CIDR表示法"""
        try:
            if '/' in ip_or_cidr:
                ipaddress.ip_network(ip_or_cidr, strict=False)
                return True
            return False
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
            return False
    
    @staticmethod
    def is_valid_ip(ip_str: str) -> bool:
        """检查字符串是否为有效IP地址"""
        try:
            ipaddress.ip_address(ip_str)
            return True
        except (ipaddress.AddressValueError, ValueError):
            return False
    
    @staticmethod
    def ip_in_cidr(ip_str: str, cidr_str: str) -> bool:
        """检查IP是否在CIDR范围内"""
        try:
            ip = ipaddress.ip_address(ip_str)
            network = ipaddress.ip_network(cidr_str, strict=False)
            return ip in network
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
            return False
    
    @staticmethod
    def normalize_cidr(ip_or_cidr: str) -> str:
        """标准化CIDR表示法，所有IP都转换为/24子网"""
        try:
            if '/' in ip_or_cidr:
                ip_str, prefix = ip_or_cidr.split('/', 1)
                ip = ipaddress.ip_address(ip_str)
                if ip.version == 4:
                    network = ipaddress.ip_network(f"{ip}/24", strict=False)
                    return str(network)
                else:
                    try:
                        network = ipaddress.ip_network(ip_or_cidr, strict=False)
                        return str(network)
                    except:
                        return f"{ip}/128"
            else:
                ip = ipaddress.ip_address(ip_or_cidr)
                if ip.version == 4:
                    network = ipaddress.ip_network(f"{ip}/24", strict=False)
                    return str(network)
                else:
                    return f"{ip}/128"
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
            return ip_or_cidr
    
    @staticmethod
    def match_ip_against_patterns(client_ip: str, stored_patterns: List[str]) -> Tuple[bool, str]:
        """
        检查客户端IP是否匹配存储的模式列表（支持CIDR和精确匹配）
        返回: (是否匹配, 匹配的模式)
        """
        if not CIDRMatcher.is_valid_ip(client_ip):
            return False, ""
        
        for pattern in stored_patterns:
            if not pattern:
                continue
                
            if CIDRMatcher.is_cidr_notation(pattern):
                if CIDRMatcher.ip_in_cidr(client_ip, pattern):
                    return True, pattern
            else:
                if client_ip == pattern:
                    return True, pattern
        
        return False, ""
    
    @staticmethod
    def expand_cidr_examples(cidr_str: str, max_examples: int = 5) -> List[str]:
        """为调试目的，展示CIDR包含的示例IP地址"""
        try:
            network = ipaddress.ip_network(cidr_str, strict=False)
            examples = []
            count = 0
            for ip in network.hosts():
                if count >= max_examples:
                    break
                examples.append(str(ip))
                count += 1
            if network.prefixlen == 32:
                examples = [str(network.network_address)]
            return examples
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
            return []
