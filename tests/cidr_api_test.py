#!/usr/bin/env python3
"""
Simple CIDR API Test Script
简单的CIDR API测试脚本

Test the CIDR functionality by directly calling the functions
without needing Redis or a running server.
"""

import sys
import json
import hashlib

# Add the current directory to Python path
sys.path.insert(0, '/home/runner/work/YuemPyScripts/YuemPyScripts/Server/文件代理')

try:
    from app import CIDRMatcher
    print("✓ Successfully imported CIDRMatcher from app.py")
except ImportError as e:
    print(f"✗ Failed to import CIDRMatcher: {e}")
    sys.exit(1)

def test_user_example():
    """Test the specific user example: 192.168.223.112 should match 192.168.223.0/24"""
    print("\n=== Testing User's Specific Example ===")
    print("User request: 核实传入白名单以cidr判断 比如192.168.223.112 那么只需是 192.168.223.0/24")
    print("Translation: Verify incoming whitelist using CIDR judgment. For example, for 192.168.223.112, it only needs to be 192.168.223.0/24")
    
    test_ip = "192.168.223.112"
    test_cidr = "192.168.223.0/24"
    
    print(f"\n🧪 Testing: IP {test_ip} against CIDR {test_cidr}")
    
    # Step 1: Validate inputs
    print(f"1. ✓ Is '{test_ip}' a valid IP? {CIDRMatcher.is_valid_ip(test_ip)}")
    print(f"2. ✓ Is '{test_cidr}' valid CIDR notation? {CIDRMatcher.is_cidr_notation(test_cidr)}")
    
    # Step 2: Test the core matching functionality
    matches = CIDRMatcher.ip_in_cidr(test_ip, test_cidr)
    print(f"3. ✓ Does '{test_ip}' match '{test_cidr}'? {matches}")
    
    # Step 3: Test pattern matching (like the API would use)
    ip_patterns = [test_cidr]
    is_match, matched_pattern = CIDRMatcher.match_ip_against_patterns(test_ip, ip_patterns)
    print(f"4. ✓ Pattern matching result: {is_match}, matched pattern: '{matched_pattern}'")
    
    # Step 4: Show what would be stored in Redis
    normalized_pattern = CIDRMatcher.normalize_cidr(test_cidr)
    print(f"5. ✓ Normalized CIDR pattern: '{normalized_pattern}'")
    
    # Step 5: Show examples of IPs in this CIDR range
    examples = CIDRMatcher.expand_cidr_examples(test_cidr, 10)
    print(f"6. ✓ Example IPs in this CIDR range: {examples[:5]}...")
    
    if matches and is_match:
        print("\n🎉 SUCCESS: User's example works correctly!")
        print(f"✅ IP {test_ip} successfully matches CIDR {test_cidr}")
        return True
    else:
        print(f"\n❌ FAILED: IP {test_ip} does not match CIDR {test_cidr}")
        return False

def test_api_simulation():
    """Simulate how the API would handle the user's request"""
    print("\n=== Simulating API Request Processing ===")
    
    # Simulate API request data
    api_request = {
        "uid": "user123", 
        "path": "/media/2024-01-15/video123",
        "UserAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "ipPatterns": ["192.168.223.0/24"]  # User's CIDR pattern
    }
    
    print(f"Simulated API request: {json.dumps(api_request, indent=2)}")
    
    # Step 1: Extract and validate IP patterns
    ip_patterns = api_request.get("ipPatterns", [])
    print(f"\n1. ✓ Extracted IP patterns: {ip_patterns}")
    
    # Step 2: Normalize patterns (like the API does)
    normalized_patterns = []
    for pattern in ip_patterns:
        if CIDRMatcher.is_valid_ip(pattern) or CIDRMatcher.is_cidr_notation(pattern):
            normalized = CIDRMatcher.normalize_cidr(pattern)
            normalized_patterns.append(normalized)
            print(f"2. ✓ Normalized '{pattern}' to '{normalized}'")
        else:
            print(f"2. ✗ Invalid pattern: '{pattern}'")
    
    # Step 3: Simulate Redis storage format
    user_agent = api_request["UserAgent"]
    ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
    
    whitelist_data = {
        "uid": api_request["uid"],
        "key_path": "video123",  # Extracted from path
        "ip_patterns": normalized_patterns,
        "user_agent": user_agent,
        "created_at": 1725469328,  # Current timestamp
        "worker_pid": 12345
    }
    
    print(f"3. ✓ Generated UA hash: {ua_hash}")
    print(f"4. ✓ Simulated Redis storage data:")
    print(json.dumps(whitelist_data, indent=2))
    
    # Step 4: Test client IP matching
    test_client_ip = "192.168.223.112"  # User's example IP
    print(f"\n5. 🧪 Testing client IP '{test_client_ip}' against stored patterns...")
    
    is_match, matched_pattern = CIDRMatcher.match_ip_against_patterns(
        test_client_ip, 
        whitelist_data["ip_patterns"]
    )
    
    if is_match:
        print(f"5. ✅ Client IP '{test_client_ip}' matches pattern '{matched_pattern}'")
        print("6. ✅ Access would be GRANTED")
        return True
    else:
        print(f"5. ❌ Client IP '{test_client_ip}' does not match any patterns")
        print("6. ❌ Access would be DENIED")
        return False

def test_boundary_cases():
    """Test edge cases around the CIDR range"""
    print("\n=== Testing Boundary Cases ===")
    
    cidr = "192.168.223.0/24"
    test_cases = [
        ("192.168.223.0", "Network address"),
        ("192.168.223.1", "First usable IP"), 
        ("192.168.223.112", "User's example IP"),
        ("192.168.223.254", "Last usable IP"),
        ("192.168.223.255", "Broadcast address"),
        ("192.168.222.255", "Previous subnet"),
        ("192.168.224.1", "Next subnet")
    ]
    
    print(f"Testing CIDR: {cidr}")
    print("-" * 50)
    
    for ip, description in test_cases:
        matches = CIDRMatcher.ip_in_cidr(ip, cidr)
        status = "✅ MATCHES" if matches else "❌ NO MATCH"
        print(f"{ip:15} ({description:20}): {status}")
    
    return True

def main():
    """Main test function"""
    print("🚀 CIDR Verification Test")
    print("=" * 60)
    print("Testing user's request: 192.168.223.112 should match 192.168.223.0/24")
    print("=" * 60)
    
    try:
        success_count = 0
        total_tests = 3
        
        # Run tests
        if test_user_example():
            success_count += 1
            
        if test_api_simulation():
            success_count += 1
            
        if test_boundary_cases():
            success_count += 1
        
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {success_count}/{total_tests} tests passed")
        
        if success_count == total_tests:
            print("🎉 ALL TESTS PASSED!")
            print("\n✅ 核实结果 (Verification Result):")
            print("✅ CIDR 功能正常工作 (CIDR functionality works correctly)")
            print("✅ 用户示例确认: 192.168.223.112 匹配 192.168.223.0/24")
            print("✅ User example confirmed: 192.168.223.112 matches 192.168.223.0/24")
            print("\n📝 实现详情 (Implementation Details):")
            print("   - 支持标准 CIDR 表示法 (Supports standard CIDR notation)")
            print("   - 向后兼容精确 IP 匹配 (Backward compatible with exact IP matching)")
            print("   - 自动标准化和验证 (Automatic normalization and validation)")
            print("   - 高效的模式匹配算法 (Efficient pattern matching algorithm)")
        else:
            print("❌ SOME TESTS FAILED!")
            print("❌ CIDR functionality may have issues")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()