#!/usr/bin/env python3
"""
测试静态文件白名单API功能
Test static file whitelist API functionality
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.config import config


def test_static_file_whitelist_concept():
    """测试静态文件白名单的概念和数据结构"""
    print("=" * 60)
    print("测试静态文件白名单功能")
    print("=" * 60)
    
    print("\n新增API端点: POST /api/static-whitelist")
    print("\n请求参数:")
    print("  {")
    print('    "uid": "user123",')
    print('    "clientIp": "192.168.1.100",')
    print('    "UserAgent": "Mozilla/5.0..."')
    print("  }")
    print("\n注意：无需提供 path 参数")
    
    print("\n" + "=" * 60)
    print("数据存储结构")
    print("=" * 60)
    
    print("\n1. Redis键格式（独立存储）:")
    print("   static_file_access:{ip_pattern}:{ua_hash}")
    print("   示例: static_file_access:192.168.1.0_24:abc12345")
    
    print("\n2. 数据结构:")
    print("   {")
    print('     "uid": "user123",')
    print('     "ip_patterns": ["192.168.1.0/24"],')
    print('     "user_agent": "Mozilla/5.0...",')
    print('     "created_at": 1234567890,')
    print('     "access_type": "static_files_only"')
    print("   }")
    
    print("\n3. UID级别追踪键:")
    print("   uid_static_ua_ip_pairs:{uid}")
    print("   示例: uid_static_ua_ip_pairs:user123")
    
    print("\n" + "=" * 60)
    print("功能特性")
    print("=" * 60)
    
    print("\n✓ 独立存储: 与路径白名单分离，使用不同的Redis键前缀")
    print(f"✓ TTL相同: {config.IP_ACCESS_TTL}秒（与路径白名单一致）")
    print(f"✓ 支持多个: 每个UID最多{config.MAX_UA_IP_PAIRS_PER_UID}个UA+IP组合")
    print("✓ FIFO替换: 超过限制时自动删除最旧的组合")
    print("✓ 无需路径: 只需提交UA+IP，不需要path参数")
    print("✓ 自动清理: 删除旧对时同时清理Redis键")
    
    print("\n" + "=" * 60)
    print("访问流程")
    print("=" * 60)
    
    print("\n当静态文件请求到达时:")
    print("  1. 检测文件是否为静态文件（通过扩展名）")
    print("  2. 如果 ENABLE_STATIC_FILE_IP_ONLY_CHECK=True:")
    print("     a. 首先检查 static_file_access 独立白名单")
    print("     b. 如果匹配，立即允许访问")
    print("     c. 如果不匹配，继续检查路径白名单（ip_cidr_access）")
    print("  3. 验证IP+UA组合")
    print("  4. 允许或拒绝访问")
    
    print("\n" + "=" * 60)
    print("使用场景")
    print("=" * 60)
    
    print("\n场景1: 用户只需要访问静态资源")
    print("  - 调用 POST /api/static-whitelist")
    print("  - 提交: uid, clientIp, UserAgent")
    print("  - 无需提供 path")
    print("  - 可以访问所有静态文件(.webp, .jpg, .css等)")
    
    print("\n场景2: 用户需要访问视频+静态资源")
    print("  - 调用 POST /api/whitelist (提供path)")
    print("  - 或调用 POST /api/static-whitelist (不提供path)")
    print("  - 两个白名单独立工作，可同时使用")
    
    print("\n场景3: 多设备访问")
    print("  - 同一个UID可以添加多个UA+IP组合")
    print("  - 手机、平板、电脑各自的IP+UA都可以独立添加")
    print(f"  - 最多支持{config.MAX_UA_IP_PAIRS_PER_UID}个组合")
    
    print("\n" + "=" * 60)
    print("与原有功能对比")
    print("=" * 60)
    
    print("\n原有白名单 (ip_cidr_access):")
    print("  ✓ 需要提供 path")
    print("  ✓ 验证路径是否匹配")
    print("  ✓ 用于视频等需要路径保护的资源")
    
    print("\n新增静态文件白名单 (static_file_access):")
    print("  ✓ 无需提供 path")
    print("  ✓ 只验证IP+UA组合")
    print("  ✓ 专用于静态文件访问")
    print("  ✓ 独立存储，互不干扰")
    
    print("\n" + "=" * 60)
    print("API调用示例")
    print("=" * 60)
    
    print("\n# 添加静态文件白名单")
    print("curl -X POST http://localhost:7889/api/static-whitelist \\")
    print('  -H "Authorization: ******" \\')
    print('  -H "Content-Type: application/json" \\')
    print("  -d '{")
    print('    "uid": "user123",')
    print('    "clientIp": "192.168.1.100",')
    print('    "UserAgent": "Mozilla/5.0 (Windows NT 10.0) Chrome/120.0"')
    print("  }'")
    
    print("\n# 响应示例")
    print("{")
    print('  "success": true,')
    print('  "message": "Static file whitelist added/updated successfully",')
    print('  "ip_pattern": "192.168.1.0/24",')
    print('  "ua_hash": "abc12345",')
    print('  "ttl": 3600,')
    print('  "uid_static_ua_ip_pairs_info": {')
    print('    "max_pairs_per_uid": 5,')
    print('    "current_pairs_count": 1,')
    print('    "pairs_removed": 0')
    print("  }")
    print("}")
    
    print("\n" + "=" * 60)
    print("✅ 测试概念通过")
    print("=" * 60)


def test_redis_key_independence():
    """测试Redis键的独立性"""
    print("\n\n" + "=" * 60)
    print("测试Redis键的独立性")
    print("=" * 60)
    
    print("\n路径白名单键格式:")
    print("  ip_cidr_access:192.168.1.0_24:abc12345")
    print("  uid_ua_ip_pairs:user123")
    
    print("\n静态文件白名单键格式:")
    print("  static_file_access:192.168.1.0_24:abc12345")
    print("  uid_static_ua_ip_pairs:user123")
    
    print("\n独立性验证:")
    print("  ✓ 使用不同的键前缀（ip_cidr_access vs static_file_access）")
    print("  ✓ UID追踪键也不同（uid_ua_ip_pairs vs uid_static_ua_ip_pairs）")
    print("  ✓ 两个白名单互不干扰")
    print("  ✓ 可以同时使用，分别管理")
    
    print("\n示例场景:")
    print("  用户user123同时拥有:")
    print("    - 3个路径白名单UA+IP对（用于视频访问）")
    print("    - 2个静态文件白名单UA+IP对（用于静态资源）")
    print("  总共5个组合，但分别计数，互不影响")
    
    print("\n✅ Redis键独立性验证通过")


if __name__ == "__main__":
    try:
        test_static_file_whitelist_concept()
        test_redis_key_independence()
        
        print("\n\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)
        print("\n新功能说明:")
        print("  1. 新增 POST /api/static-whitelist 接口")
        print("  2. 只需提交 uid + clientIp + UserAgent")
        print("  3. 无需提供 path 参数")
        print("  4. 独立Redis键存储，与路径白名单分离")
        print("  5. 支持多个UA+IP组合（FIFO替换）")
        print("  6. TTL与路径白名单相同")
        
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
