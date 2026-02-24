#!/usr/bin/env python3
"""
演示脚本：展示如何使用两种API Key格式
Demonstration script showing both API key formats
"""

def demonstrate_api_usage():
    """演示两种API Key格式的使用方法"""
    
    print("=" * 70)
    print("文件检查API - 支持两种认证格式")
    print("File Check API - Supporting Two Authentication Formats")
    print("=" * 70)
    print()
    
    # 格式1：标准Bearer格式（推荐）
    print("✅ 格式1: 标准Bearer格式 (推荐)")
    print("   Format 1: Standard Bearer Format (Recommended)")
    print("-" * 70)
    print("curl -X POST https://spcs.yuelk.com/api/file/check \\")
    print('  -H "Authorization: Bearer F2UkWEJZRBxC7" \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"path": "video/2025-06-17/6a21d6c449_RrOLsf/preview/index.m3u8"}\'')
    print()
    
    # 格式2：简化格式
    print("✅ 格式2: 简化格式")
    print("   Format 2: Simplified Format")
    print("-" * 70)
    print("curl -X POST https://spcs.yuelk.com/api/file/check \\")
    print('  -H "Authorization: F2UkWEJZRBxC7" \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"path": "video/2025-06-17/6a21d6c449_RrOLsf/preview/index.m3u8"}\'')
    print()
    
    print("=" * 70)
    print("问题解决说明 (Problem Resolution)")
    print("=" * 70)
    print()
    print("原问题 (Original Issue):")
    print("  用户使用了简化格式，但之前的代码只支持Bearer格式")
    print("  User used simplified format, but previous code only supported Bearer format")
    print()
    print("解决方案 (Solution):")
    print("  修改代码以支持两种格式，提供更好的兼容性")
    print("  Modified code to support both formats for better compatibility")
    print()
    print("现在两种格式都可以正常工作！")
    print("Now both formats work correctly!")
    print("=" * 70)


if __name__ == "__main__":
    demonstrate_api_usage()
