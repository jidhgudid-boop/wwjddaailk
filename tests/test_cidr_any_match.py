#!/usr/bin/env python3
"""
验证IP匹配逻辑：只要找到任何一个CIDR范围就算成功
Verify IP matching: finding ANY CIDR range counts as success
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.cidr_matcher import CIDRMatcher


def test_ip_match_any_cidr():
    """测试IP匹配任意一个CIDR范围即成功"""
    print("=" * 60)
    print("测试IP匹配逻辑：只要找到任何一个CIDR范围就算成功")
    print("=" * 60)
    
    # 测试场景1：多个CIDR范围，IP匹配第一个
    print("\n场景1：多个CIDR范围，IP匹配第一个")
    patterns = ["192.168.1.0/24", "10.0.0.0/24", "172.16.0.0/24"]
    test_ip = "192.168.1.100"
    
    is_match, matched_pattern = CIDRMatcher.match_ip_against_patterns(test_ip, patterns)
    print(f"  IP: {test_ip}")
    print(f"  CIDR范围: {patterns}")
    print(f"  匹配结果: {is_match}")
    print(f"  匹配的范围: {matched_pattern}")
    assert is_match, "应该匹配第一个CIDR范围"
    assert matched_pattern == "192.168.1.0/24", "应该返回匹配的CIDR"
    print("  ✅ 通过：匹配第一个CIDR即返回成功")
    
    # 测试场景2：多个CIDR范围，IP匹配中间的
    print("\n场景2：多个CIDR范围，IP匹配中间的")
    patterns = ["192.168.1.0/24", "10.0.0.0/24", "172.16.0.0/24"]
    test_ip = "10.0.0.50"
    
    is_match, matched_pattern = CIDRMatcher.match_ip_against_patterns(test_ip, patterns)
    print(f"  IP: {test_ip}")
    print(f"  CIDR范围: {patterns}")
    print(f"  匹配结果: {is_match}")
    print(f"  匹配的范围: {matched_pattern}")
    assert is_match, "应该匹配第二个CIDR范围"
    assert matched_pattern == "10.0.0.0/24", "应该返回匹配的CIDR"
    print("  ✅ 通过：匹配任意一个CIDR即返回成功")
    
    # 测试场景3：多个CIDR范围，IP匹配最后一个
    print("\n场景3：多个CIDR范围，IP匹配最后一个")
    patterns = ["192.168.1.0/24", "10.0.0.0/24", "172.16.0.0/24"]
    test_ip = "172.16.0.200"
    
    is_match, matched_pattern = CIDRMatcher.match_ip_against_patterns(test_ip, patterns)
    print(f"  IP: {test_ip}")
    print(f"  CIDR范围: {patterns}")
    print(f"  匹配结果: {is_match}")
    print(f"  匹配的范围: {matched_pattern}")
    assert is_match, "应该匹配第三个CIDR范围"
    assert matched_pattern == "172.16.0.0/24", "应该返回匹配的CIDR"
    print("  ✅ 通过：遍历所有CIDR直到找到匹配")
    
    # 测试场景4：多个CIDR范围，IP不匹配任何一个
    print("\n场景4：多个CIDR范围，IP不匹配任何一个")
    patterns = ["192.168.1.0/24", "10.0.0.0/24", "172.16.0.0/24"]
    test_ip = "8.8.8.8"
    
    is_match, matched_pattern = CIDRMatcher.match_ip_against_patterns(test_ip, patterns)
    print(f"  IP: {test_ip}")
    print(f"  CIDR范围: {patterns}")
    print(f"  匹配结果: {is_match}")
    print(f"  匹配的范围: {matched_pattern}")
    assert not is_match, "不应该匹配任何CIDR范围"
    assert matched_pattern == "", "不匹配时应该返回空字符串"
    print("  ✅ 通过：不匹配任何CIDR时返回失败")
    
    # 测试场景5：单个CIDR范围
    print("\n场景5：单个CIDR范围")
    patterns = ["192.168.1.0/24"]
    test_ip = "192.168.1.150"
    
    is_match, matched_pattern = CIDRMatcher.match_ip_against_patterns(test_ip, patterns)
    print(f"  IP: {test_ip}")
    print(f"  CIDR范围: {patterns}")
    print(f"  匹配结果: {is_match}")
    print(f"  匹配的范围: {matched_pattern}")
    assert is_match, "应该匹配单个CIDR范围"
    assert matched_pattern == "192.168.1.0/24", "应该返回匹配的CIDR"
    print("  ✅ 通过：单个CIDR也能正确匹配")
    
    # 测试场景6：混合CIDR和精确IP
    print("\n场景6：混合CIDR和精确IP")
    patterns = ["192.168.1.0/24", "8.8.8.8", "10.0.0.0/24"]
    test_ip = "8.8.8.8"
    
    is_match, matched_pattern = CIDRMatcher.match_ip_against_patterns(test_ip, patterns)
    print(f"  IP: {test_ip}")
    print(f"  模式: {patterns}")
    print(f"  匹配结果: {is_match}")
    print(f"  匹配的模式: {matched_pattern}")
    assert is_match, "应该匹配精确IP"
    assert matched_pattern == "8.8.8.8", "应该返回匹配的IP"
    print("  ✅ 通过：支持精确IP匹配")
    
    # 测试场景7：空模式列表
    print("\n场景7：空模式列表")
    patterns = []
    test_ip = "192.168.1.100"
    
    is_match, matched_pattern = CIDRMatcher.match_ip_against_patterns(test_ip, patterns)
    print(f"  IP: {test_ip}")
    print(f"  模式: {patterns}")
    print(f"  匹配结果: {is_match}")
    assert not is_match, "空模式列表不应该匹配"
    print("  ✅ 通过：空模式列表返回失败")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过")
    print("=" * 60)
    print("\n结论：")
    print("  ✓ IP匹配逻辑正确：只要找到任何一个CIDR范围就算成功")
    print("  ✓ 遍历所有模式，找到第一个匹配即返回True")
    print("  ✓ 支持CIDR范围和精确IP混合匹配")
    print("  ✓ 不匹配任何模式时返回False")


def test_auth_service_integration():
    """测试auth_service中的集成逻辑"""
    print("\n\n" + "=" * 60)
    print("auth_service集成逻辑说明")
    print("=" * 60)
    
    print("\n当前实现流程:")
    print("  1. 根据UA hash查找所有匹配的Redis键: ip_cidr_access:*:{ua_hash}")
    print("  2. 遍历每个找到的键:")
    print("     a. 获取该键的 ip_patterns 列表")
    print("     b. 调用 CIDRMatcher.match_ip_against_patterns(client_ip, ip_patterns)")
    print("     c. 如果IP匹配任何一个pattern，返回True")
    print("  3. 对于静态文件且启用IP-only验证:")
    print("     - 找到IP匹配即返回成功（无需路径验证）")
    print("  4. 对于非静态文件:")
    print("     - 找到IP匹配后，继续验证路径是否匹配")
    print("     - 路径也匹配才返回成功")
    
    print("\n关键点:")
    print("  ✓ IP匹配：只要在 ip_patterns 中找到任何一个CIDR/IP匹配即可")
    print("  ✓ UA匹配：通过Redis键中的ua_hash确保UA一致")
    print("  ✓ 路径匹配：非静态文件需要额外验证路径")
    
    print("\n示例:")
    print("  Redis键: ip_cidr_access:192.168.1.0_24:abc12345")
    print("  数据: {")
    print("    'uid': 'user123',")
    print("    'ip_patterns': ['192.168.1.0/24', '10.0.0.0/24'],  # 多个CIDR")
    print("    'paths': [{'key_path': 'video/abc'}]")
    print("  }")
    print("\n  请求: IP=192.168.1.100, UA对应abc12345")
    print("  结果: IP匹配第一个CIDR (192.168.1.0/24) ✓")
    print("\n  请求: IP=10.0.0.50, UA对应abc12345")
    print("  结果: IP匹配第二个CIDR (10.0.0.0/24) ✓")
    print("\n  请求: IP=172.16.0.1, UA对应abc12345")
    print("  结果: IP不匹配任何CIDR ✗")


if __name__ == "__main__":
    try:
        test_ip_match_any_cidr()
        test_auth_service_integration()
        
        print("\n" + "=" * 60)
        print("验证完成：IP匹配逻辑工作正常")
        print("只要找到任何一个CIDR范围就算成功 ✅")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
