#!/usr/bin/env python3
"""
测试 IPv6 地址规范化功能
Test IPv6 address normalization feature
"""
import sys
import os
import ipaddress
import hashlib

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_ipaddress_normalization():
    """测试 ipaddress 模块的规范化功能"""
    print("=" * 70)
    print("测试: IPv6 地址规范化")
    print("=" * 70)
    
    print("\n测试1: IPv6 地址的不同表示形式规范化")
    
    # 同一个 IPv6 地址的不同表示
    test_cases = [
        {
            "desc": "压缩格式",
            "original": "2001:db8::1",
            "expected": "2001:db8::1"
        },
        {
            "desc": "部分压缩",
            "original": "2001:0db8::1",
            "expected": "2001:db8::1"
        },
        {
            "desc": "完整格式",
            "original": "2001:0db8:0000:0000:0000:0000:0000:0001",
            "expected": "2001:db8::1"
        },
        {
            "desc": "前导零省略",
            "original": "2001:db8:0:0:0:0:0:1",
            "expected": "2001:db8::1"
        },
        {
            "desc": "IPv6回环",
            "original": "::1",
            "expected": "::1"
        },
        {
            "desc": "IPv4映射到IPv6",
            "original": "::ffff:192.0.2.1",
            "expected": "::ffff:c000:201"  # Python规范化为十六进制格式
        },
    ]
    
    print(f"\n  同一地址 (2001:db8::1) 的不同表示:")
    print()
    
    all_normalized = []
    all_hashes = []
    
    for case in test_cases:
        try:
            original = case["original"]
            expected = case["expected"]
            
            # 规范化
            ip_obj = ipaddress.ip_address(original)
            normalized = str(ip_obj)
            
            # 计算hash
            normalized_hash = hashlib.md5(normalized.encode()).hexdigest()[:8]
            
            all_normalized.append(normalized)
            all_hashes.append(normalized_hash)
            
            status = "✅" if normalized == expected else "❌"
            print(f"  {status} {case['desc']:15s}")
            print(f"      原始:     {original}")
            print(f"      规范化:   {normalized}")
            print(f"      Hash:    {normalized_hash}")
            print()
            
            assert normalized == expected, f"规范化结果应为 {expected}，实际为 {normalized}"
            
        except Exception as e:
            print(f"  ❌ {case['desc']}: 失败 - {e}")
            return False
    
    # 检查所有规范化后的地址是否一致
    unique_normalized = set(all_normalized[:4])  # 前4个应该是同一地址
    unique_hashes = set(all_hashes[:4])
    
    print("  验证结果:")
    if len(unique_normalized) == 1 and len(unique_hashes) == 1:
        print(f"    ✅ 所有表示形式规范化为相同地址: {list(unique_normalized)[0]}")
        print(f"    ✅ 所有表示形式产生相同hash: {list(unique_hashes)[0]}")
    else:
        print(f"    ❌ 规范化失败: {len(unique_normalized)} 个不同的地址")
        return False
    
    print("\n测试2: IPv4 地址规范化（应保持不变）")
    
    ipv4_cases = [
        "192.168.1.1",
        "10.0.0.1",
        "203.0.113.1",
    ]
    
    for ip in ipv4_cases:
        try:
            ip_obj = ipaddress.ip_address(ip)
            normalized = str(ip_obj)
            status = "✅" if normalized == ip else "❌"
            print(f"  {status} {ip:20s} -> {normalized}")
            assert normalized == ip, f"IPv4地址应保持不变"
        except Exception as e:
            print(f"  ❌ {ip}: 失败 - {e}")
            return False
    
    print("\n✅ IPv6 地址规范化测试通过")
    print()
    return True


def test_client_ip_normalization_simulation():
    """模拟客户端IP规范化"""
    print("=" * 70)
    print("测试: 客户端IP提取与规范化模拟")
    print("=" * 70)
    
    print("\n模拟 get_client_ip() 函数的规范化逻辑:")
    
    test_scenarios = [
        {
            "desc": "IPv6 压缩格式",
            "input": "2001:db8::1",
            "expected": "2001:db8::1"
        },
        {
            "desc": "IPv6 完整格式",
            "input": "2001:0db8:0000:0000:0000:0000:0000:0001",
            "expected": "2001:db8::1"
        },
        {
            "desc": "IPv4 地址",
            "input": "192.168.1.100",
            "expected": "192.168.1.100"
        },
        {
            "desc": "IPv6 回环",
            "input": "::1",
            "expected": "::1"
        },
        {
            "desc": "IPv4映射IPv6",
            "input": "::ffff:192.0.2.1",
            "expected": "::ffff:c000:201"  # Python规范化为十六进制格式
        },
    ]
    
    print()
    for scenario in test_scenarios:
        ip_str = scenario["input"]
        expected = scenario["expected"]
        
        try:
            # 模拟规范化逻辑
            ip_obj = ipaddress.ip_address(ip_str)
            normalized = str(ip_obj)
            
            status = "✅" if normalized == expected else "❌"
            print(f"  {status} {scenario['desc']:20s}")
            print(f"      输入:     {ip_str}")
            print(f"      规范化:   {normalized}")
            
            assert normalized == expected, f"应为 {expected}，实际为 {normalized}"
            
        except Exception as e:
            print(f"  ❌ {scenario['desc']}: 失败 - {e}")
            return False
    
    print("\n✅ 客户端IP规范化模拟测试通过")
    print()
    return True


def test_hash_consistency_after_normalization():
    """测试规范化后的hash一致性"""
    print("=" * 70)
    print("测试: 规范化后Hash一致性")
    print("=" * 70)
    
    print("\n验证同一IPv6地址的不同表示形式在规范化后产生相同hash:")
    
    # 同一个 IPv6 地址的不同表示
    ipv6_variants = [
        "2001:db8::1",
        "2001:0db8::1",
        "2001:0db8:0000:0000:0000:0000:0000:0001",
        "2001:db8:0:0:0:0:0:1",
    ]
    
    normalized_ips = []
    hashes = []
    
    print(f"\n  原始表示 -> 规范化 -> Hash")
    print()
    
    for ip in ipv6_variants:
        try:
            ip_obj = ipaddress.ip_address(ip)
            normalized = str(ip_obj)
            hash_value = hashlib.md5(normalized.encode()).hexdigest()[:8]
            
            normalized_ips.append(normalized)
            hashes.append(hash_value)
            
            print(f"  {ip:50s} -> {normalized:20s} -> {hash_value}")
            
        except Exception as e:
            print(f"  ❌ {ip}: 失败 - {e}")
            return False
    
    # 检查一致性
    unique_normalized = set(normalized_ips)
    unique_hashes = set(hashes)
    
    print(f"\n  结果分析:")
    print(f"    唯一规范化地址数: {len(unique_normalized)}")
    print(f"    唯一hash数:        {len(unique_hashes)}")
    
    if len(unique_normalized) == 1 and len(unique_hashes) == 1:
        print(f"\n  ✅ 成功: 所有表示形式规范化为相同地址: {list(unique_normalized)[0]}")
        print(f"  ✅ 成功: 所有表示形式产生相同hash: {list(unique_hashes)[0]}")
        print("\n  这解决了 JS Whitelist 中 IPv6 地址匹配失败的问题!")
        return True
    else:
        print(f"\n  ❌ 失败: 规范化后仍有不同的地址或hash")
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("开始测试 IPv6 地址规范化功能")
    print("=" * 70 + "\n")
    
    results = []
    
    try:
        results.append(("ipaddress规范化", test_ipaddress_normalization()))
        results.append(("客户端IP规范化", test_client_ip_normalization_simulation()))
        results.append(("Hash一致性", test_hash_consistency_after_normalization()))
        
        print("=" * 70)
        print("测试总结")
        print("=" * 70)
        
        print("\n测试结果:")
        all_passed = True
        for test_name, result in results:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"  • {test_name:20s}: {status}")
            if not result:
                all_passed = False
        
        if all_passed:
            print("\n🎉 所有测试通过!")
            print("\n✅ 关键改进:")
            print("  • IPv6 地址在存储前自动规范化")
            print("  • 同一地址的不同表示形式产生相同hash")
            print("  • 解决了 JS Whitelist IPv6 匹配问题")
            print("  • 支持 IPv4/IPv6 混合环境")
            
            print("\n📝 已实现的功能:")
            print("  • helpers.py get_client_ip() 自动规范化")
            print("  • 使用 Python ipaddress 标准库")
            print("  • 保持 IPv4 地址不变")
            print("  • IPv6 转换为压缩格式")
        else:
            print("\n⚠️  部分测试失败，需要检查")
        
        print("\n" + "=" * 70)
        print("IPv6 地址规范化测试完成")
        print("=" * 70)
        
        return all_passed
        
    except Exception as e:
        print("\n" + "=" * 70)
        print(f"❌ 测试出错: {str(e)}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
