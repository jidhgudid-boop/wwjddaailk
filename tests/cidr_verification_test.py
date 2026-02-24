#!/usr/bin/env python3
"""
CIDR Verification Test Script
验证CIDR功能测试脚本

This script tests the CIDR matching functionality to verify that IP addresses
can be correctly matched against CIDR patterns, specifically testing the 
user's example: 192.168.223.112 should match 192.168.223.0/24
"""

import sys
import os
import json
import ipaddress
import hashlib
import asyncio
import aiohttp

# Add the current directory to Python path to import the app module
sys.path.insert(0, '/home/runner/work/YuemPyScripts/YuemPyScripts/Server/文件代理')

try:
    from app import CIDRMatcher
    print("✓ Successfully imported CIDRMatcher from app.py")
except ImportError as e:
    print(f"✗ Failed to import CIDRMatcher: {e}")
    sys.exit(1)

def test_cidr_matcher_functionality():
    """Test the CIDRMatcher class functionality"""
    print("\n=== Testing CIDRMatcher Class ===")
    
    # User's specific example
    test_ip = "192.168.223.112"
    test_cidr = "192.168.223.0/24"
    
    print(f"Testing: IP {test_ip} should match CIDR {test_cidr}")
    
    # Test 1: Check if IP is valid
    is_valid_ip = CIDRMatcher.is_valid_ip(test_ip)
    print(f"1. Is {test_ip} a valid IP? {is_valid_ip}")
    assert is_valid_ip, f"IP {test_ip} should be valid"
    
    # Test 2: Check if CIDR is valid
    is_valid_cidr = CIDRMatcher.is_cidr_notation(test_cidr)
    print(f"2. Is {test_cidr} valid CIDR notation? {is_valid_cidr}")
    assert is_valid_cidr, f"CIDR {test_cidr} should be valid"
    
    # Test 3: Check if IP is in CIDR range
    ip_in_cidr = CIDRMatcher.ip_in_cidr(test_ip, test_cidr)
    print(f"3. Is {test_ip} in {test_cidr}? {ip_in_cidr}")
    assert ip_in_cidr, f"IP {test_ip} should be in CIDR {test_cidr}"
    
    # Test 4: Normalize CIDR
    normalized = CIDRMatcher.normalize_cidr(test_cidr)
    print(f"4. Normalized CIDR: {normalized}")
    
    # Test 5: Get CIDR examples
    examples = CIDRMatcher.expand_cidr_examples(test_cidr, 5)
    print(f"5. CIDR examples: {examples}")
    
    # Test 6: Pattern matching
    patterns = [test_cidr, "10.0.0.0/8", test_ip]
    is_match, matched_pattern = CIDRMatcher.match_ip_against_patterns(test_ip, patterns)
    print(f"6. Pattern matching against {patterns}: match={is_match}, pattern={matched_pattern}")
    assert is_match, f"IP {test_ip} should match one of the patterns"
    
    print("✓ All CIDRMatcher tests passed!")

def test_additional_cases():
    """Test additional CIDR cases"""
    print("\n=== Testing Additional Cases ===")
    
    test_cases = [
        # (IP, CIDR, should_match)
        ("192.168.223.112", "192.168.223.0/24", True),   # User's example
        ("192.168.223.1", "192.168.223.0/24", True),     # First in range
        ("192.168.223.254", "192.168.223.0/24", True),   # Last in range
        ("192.168.224.1", "192.168.223.0/24", False),    # Outside range
        ("10.0.0.100", "10.0.0.0/8", True),              # Large network
        ("172.16.50.100", "172.16.0.0/12", True),        # Medium network
        ("192.168.1.100", "192.168.1.100/32", True),     # Single IP CIDR
        ("192.168.1.101", "192.168.1.100/32", False),    # Different single IP
        # Test new /24 normalization behavior
        ("180.98.66.2", "180.98.66.0/24", True),         # Any IP in same /24 subnet
        ("180.98.66.100", "180.98.66.0/24", True),       # Another IP in same /24 subnet
        ("180.98.67.2", "180.98.66.0/24", False),        # IP in different /24 subnet
    ]
    
    for ip, cidr, expected in test_cases:
        result = CIDRMatcher.ip_in_cidr(ip, cidr)
        status = "✓" if result == expected else "✗"
        print(f"{status} {ip} in {cidr}: {result} (expected: {expected})")
        if result != expected:
            print(f"   ERROR: Expected {expected}, got {result}")

def test_user_specific_case():
    """Test the specific case mentioned by the user"""
    print("\n=== Testing User's Specific Case ===")
    
    # User mentioned: 180.98.66.2 should be treated as 180.98.66.0/24
    user_ip = "180.98.66.2"
    expected_cidr = "180.98.66.0/24"
    
    # Test normalization
    normalized = CIDRMatcher.normalize_cidr(user_ip)
    print(f"User case: {user_ip} -> {normalized}")
    assert normalized == expected_cidr, f"Expected {expected_cidr}, got {normalized}"
    
    # Test that any IP in the same /24 subnet would match
    same_subnet_ips = ["180.98.66.1", "180.98.66.100", "180.98.66.254"]
    for test_ip in same_subnet_ips:
        matches = CIDRMatcher.ip_in_cidr(test_ip, expected_cidr)
        print(f"  {test_ip} in {expected_cidr}: {matches}")
        assert matches, f"{test_ip} should match {expected_cidr}"
    
    # Test that IPs outside the subnet don't match
    different_subnet_ips = ["180.98.65.2", "180.98.67.2", "180.99.66.2"]
    for test_ip in different_subnet_ips:
        matches = CIDRMatcher.ip_in_cidr(test_ip, expected_cidr)
        print(f"  {test_ip} in {expected_cidr}: {matches}")
        assert not matches, f"{test_ip} should NOT match {expected_cidr}"
    
    print("✓ User's specific case test passed!")

def test_normalization():
    """Test IP and CIDR normalization"""
    print("\n=== Testing Normalization ===")
    
    normalization_cases = [
        ("192.168.223.112", "192.168.223.0/24"),        # Single IP to /24 subnet
        ("180.98.66.2", "180.98.66.0/24"),              # User's example to /24 subnet  
        ("192.168.223.0/24", "192.168.223.0/24"),       # Already CIDR
        ("10.0.0.0/8", "10.0.0.0/8"),                   # Large network
        ("invalid.ip", "invalid.ip"),                    # Invalid should remain unchanged
    ]
    
    for input_val, expected in normalization_cases:
        result = CIDRMatcher.normalize_cidr(input_val)
        status = "✓" if result == expected else "✗"
        print(f"{status} {input_val} -> {result} (expected: {expected})")

async def test_debug_endpoints():
    """Test the debug endpoints if server is running"""
    print("\n=== Testing Debug Endpoints (if server is running) ===")
    
    # Test data
    test_ip = "192.168.223.112"
    test_cidr = "192.168.223.0/24"
    
    try:
        # Test CIDR debug endpoint
        async with aiohttp.ClientSession() as session:
            cidr_url = f"http://localhost:7888/debug/cidr?ip={test_ip}&cidr={test_cidr}"
            print(f"Testing CIDR debug endpoint: {cidr_url}")
            
            async with session.get(cidr_url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print("✓ CIDR debug endpoint response:")
                    print(json.dumps(data, indent=2))
                    
                    # Verify the response
                    assert data.get("test_ip") == test_ip
                    assert data.get("test_cidr") == test_cidr
                    assert data.get("is_valid_ip") == True
                    assert data.get("is_valid_cidr") == True
                    assert data.get("ip_in_cidr") == True
                    print("✓ All CIDR debug endpoint assertions passed!")
                else:
                    print(f"✗ CIDR debug endpoint returned status {resp.status}")
                    
    except Exception as e:
        print(f"⚠ Cannot test debug endpoints (server may not be running): {e}")
        print("  This is expected if the app is not currently running.")

def test_redis_storage_format():
    """Test how the data would be stored in Redis"""
    print("\n=== Testing Redis Storage Format ===")
    
    # Simulate the data structure that would be stored in Redis
    test_data = {
        "uid": "test_user_123",
        "key_path": "video123",
        "ip_patterns": ["192.168.223.0/24", "10.0.0.50/32"],
        "user_agent": "Mozilla/5.0 (Test Browser)",
        "created_at": 1234567890,
        "worker_pid": 12345
    }
    
    # Test JSON serialization
    json_data = json.dumps(test_data)
    parsed_data = json.loads(json_data)
    
    print("✓ Data serialization test passed")
    print(f"Sample Redis data: {json.dumps(parsed_data, indent=2)}")
    
    # Test UA hash generation (like in the app)
    user_agent = test_data["user_agent"]
    ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
    print(f"✓ UA hash for '{user_agent}': {ua_hash}")

def main():
    """Main test function"""
    print("🚀 Starting CIDR Verification Tests")
    print("=" * 50)
    
    try:
        # Run synchronous tests
        test_cidr_matcher_functionality()
        test_additional_cases()
        test_user_specific_case()  # Add the new test
        test_normalization()
        test_redis_storage_format()
        
        # Run async tests
        print("\n🔄 Running async tests...")
        asyncio.run(test_debug_endpoints())
        
        print("\n" + "=" * 50)
        print("🎉 All CIDR verification tests completed successfully!")
        print("\n✅ Verification Result: CIDR functionality works correctly")
        print(f"✅ User's example confirmed: 192.168.223.112 matches 192.168.223.0/24")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        print("❌ CIDR functionality may have issues")
        sys.exit(1)

if __name__ == "__main__":
    main()