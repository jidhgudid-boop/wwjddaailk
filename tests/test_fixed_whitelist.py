#!/usr/bin/env python3
"""
测试固定白名单功能
Test fixed IP whitelist functionality
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.config import config
from utils.cidr_matcher import CIDRMatcher


def is_ip_in_fixed_whitelist_test(client_ip: str, fixed_whitelist: list) -> bool:
    """
    测试版本的is_ip_in_fixed_whitelist函数
    不依赖Redis等外部服务
    """
    if not fixed_whitelist:
        return False
    
    try:
        is_match, matched_pattern = CIDRMatcher.match_ip_against_patterns(
            client_ip, 
            fixed_whitelist
        )
        if is_match:
            print(f"  ✅ 固定白名单验证成功: IP={client_ip} 匹配模式={matched_pattern}")
            return True
        return False
    except Exception as e:
        print(f"  ❌ 检查固定白名单失败: IP={client_ip}, error={str(e)}")
        return False


def test_fixed_whitelist_empty():
    """测试空白名单"""
    print("=" * 60)
    print("测试空白名单")
    print("=" * 60)
    
    # 测试任何IP都不应该在空白名单中
    result = is_ip_in_fixed_whitelist_test("192.168.1.1", [])
    assert result == False, "空白名单应该拒绝所有IP"
    
    result = is_ip_in_fixed_whitelist_test("10.0.0.1", [])
    assert result == False, "空白名单应该拒绝所有IP"
    
    print("✅ 空白名单测试通过")
    print()


def test_fixed_whitelist_single_ip():
    """测试单个IP"""
    print("=" * 60)
    print("测试单个IP")
    print("=" * 60)
    
    whitelist = ["192.168.1.100"]
    
    # 测试精确匹配
    result = is_ip_in_fixed_whitelist_test("192.168.1.100", whitelist)
    assert result == True, "精确匹配的IP应该在白名单中"
    
    # 测试不匹配
    result = is_ip_in_fixed_whitelist_test("192.168.1.101", whitelist)
    assert result == False, "不匹配的IP不应该在白名单中"
    
    result = is_ip_in_fixed_whitelist_test("10.0.0.1", whitelist)
    assert result == False, "不匹配的IP不应该在白名单中"
    
    print("✅ 单个IP测试通过")
    print()


def test_fixed_whitelist_cidr():
    """测试CIDR范围"""
    print("=" * 60)
    print("测试CIDR范围")
    print("=" * 60)
    
    whitelist = ["192.168.1.0/24"]
    
    # 测试范围内的IP
    result = is_ip_in_fixed_whitelist_test("192.168.1.1", whitelist)
    assert result == True, "192.168.1.1 应该在 192.168.1.0/24 范围内"
    
    result = is_ip_in_fixed_whitelist_test("192.168.1.100", whitelist)
    assert result == True, "192.168.1.100 应该在 192.168.1.0/24 范围内"
    
    result = is_ip_in_fixed_whitelist_test("192.168.1.254", whitelist)
    assert result == True, "192.168.1.254 应该在 192.168.1.0/24 范围内"
    
    # 测试范围外的IP
    result = is_ip_in_fixed_whitelist_test("192.168.2.1", whitelist)
    assert result == False, "192.168.2.1 不应该在 192.168.1.0/24 范围内"
    
    result = is_ip_in_fixed_whitelist_test("10.0.0.1", whitelist)
    assert result == False, "10.0.0.1 不应该在 192.168.1.0/24 范围内"
    
    print("✅ CIDR范围测试通过")
    print()


def test_fixed_whitelist_multiple():
    """测试多个IP和CIDR"""
    print("=" * 60)
    print("测试多个IP和CIDR")
    print("=" * 60)
    
    whitelist = [
        "192.168.1.0/24",
        "10.0.0.1",
        "172.16.0.0/16"
    ]
    
    # 测试第一个CIDR范围
    result = is_ip_in_fixed_whitelist_test("192.168.1.50", whitelist)
    assert result == True, "192.168.1.50 应该在 192.168.1.0/24 范围内"
    
    # 测试第二个单独IP
    result = is_ip_in_fixed_whitelist_test("10.0.0.1", whitelist)
    assert result == True, "10.0.0.1 应该在白名单中"
    
    # 测试第三个CIDR范围
    result = is_ip_in_fixed_whitelist_test("172.16.5.5", whitelist)
    assert result == True, "172.16.5.5 应该在 172.16.0.0/16 范围内"
    
    result = is_ip_in_fixed_whitelist_test("172.16.255.255", whitelist)
    assert result == True, "172.16.255.255 应该在 172.16.0.0/16 范围内"
    
    # 测试不在任何白名单中的IP
    result = is_ip_in_fixed_whitelist_test("8.8.8.8", whitelist)
    assert result == False, "8.8.8.8 不应该在白名单中"
    
    result = is_ip_in_fixed_whitelist_test("172.17.0.1", whitelist)
    assert result == False, "172.17.0.1 不应该在白名单中"
    
    print("✅ 多个IP和CIDR测试通过")
    print()


def test_fixed_whitelist_localhost():
    """测试本地回环地址"""
    print("=" * 60)
    print("测试本地回环地址")
    print("=" * 60)
    
    whitelist = ["127.0.0.1", "::1"]
    
    # 测试IPv4回环地址
    result = is_ip_in_fixed_whitelist_test("127.0.0.1", whitelist)
    assert result == True, "127.0.0.1 应该在白名单中"
    
    # IPv6测试可能会因为环境不同而有所不同，所以只测试IPv4
    
    print("✅ 本地回环地址测试通过")
    print()


def test_config_default():
    """测试默认配置"""
    print("=" * 60)
    print("测试默认配置")
    print("=" * 60)
    
    # 检查FIXED_IP_WHITELIST是否存在且默认为空列表
    assert hasattr(config, 'FIXED_IP_WHITELIST'), "config应该有FIXED_IP_WHITELIST属性"
    assert isinstance(config.FIXED_IP_WHITELIST, list), "FIXED_IP_WHITELIST应该是一个列表"
    
    print(f"✅ FIXED_IP_WHITELIST 存在且类型正确")
    print(f"   当前值: {config.FIXED_IP_WHITELIST}")
    print()


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("开始测试固定白名单功能")
    print("=" * 60 + "\n")
    
    try:
        test_config_default()
        test_fixed_whitelist_empty()
        test_fixed_whitelist_single_ip()
        test_fixed_whitelist_cidr()
        test_fixed_whitelist_multiple()
        test_fixed_whitelist_localhost()
        
        print("=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        return True
    except AssertionError as e:
        print("\n" + "=" * 60)
        print(f"❌ 测试失败: {str(e)}")
        print("=" * 60)
        return False
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ 测试出错: {str(e)}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
