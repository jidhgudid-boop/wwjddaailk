#!/usr/bin/env python3
"""
完全放行文件扩展名配置示例
演示如何使用 FULLY_ALLOWED_EXTENSIONS 配置
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.config import config


def demonstrate_configuration():
    """演示配置的使用"""
    print("=" * 70)
    print("完全放行文件扩展名配置示例")
    print("=" * 70)
    print()
    
    # 显示当前配置
    print("📋 当前配置:")
    print(f"  FULLY_ALLOWED_EXTENSIONS = {config.FULLY_ALLOWED_EXTENSIONS}")
    print(f"  ENABLE_STATIC_FILE_IP_ONLY_CHECK = {config.ENABLE_STATIC_FILE_IP_ONLY_CHECK}")
    print()
    
    # 测试各种文件路径
    test_cases = [
        # (路径, 描述, 预期结果)
        ("/videos/episode1/segment001.ts", "HLS 视频分片", True),
        ("/videos/episode1/segment002.ts", "HLS 视频分片", True),
        ("/images/poster.webp", "WebP 海报图", True),
        ("/images/thumbnail.webp", "WebP 缩略图", True),
        ("/api/handler.php", "PHP API 处理器", True),
        ("/videos/playlist.m3u8", "M3U8 播放列表", False),
        ("/videos/enc.key", "加密密钥", False),
        ("/static/app.js", "JavaScript 文件", False),
        ("/static/style.css", "CSS 样式文件", False),
        ("/images/photo.jpg", "JPEG 图片", False),
        ("/images/icon.png", "PNG 图标", False),
    ]
    
    print("🧪 测试文件路径验证逻辑:")
    print("-" * 70)
    print(f"{'状态':^10} | {'文件路径':^35} | {'描述'}")
    print("-" * 70)
    
    skip_count = 0
    validate_count = 0
    
    for path, description, expected_skip in test_cases:
        # 模拟 routes/proxy.py 中的逻辑
        if config.ENABLE_STATIC_FILE_IP_ONLY_CHECK:
            skip_validation = path.lower().endswith(config.FULLY_ALLOWED_EXTENSIONS)
        else:
            skip_validation_suffixes = (
                '.webp', '.php', '.js', '.css', '.ico', '.txt',
                '.woff', '.woff2', '.ttf', '.png', '.jpg', '.jpeg', '.gif', '.svg'
            )
            skip_validation = path.lower().endswith(skip_validation_suffixes)
        
        if skip_validation:
            skip_count += 1
            status = "🔓 跳过"
        else:
            validate_count += 1
            status = "🔒 验证"
        
        # 验证预期结果
        if skip_validation == expected_skip:
            result_marker = "✅"
        else:
            result_marker = "❌"
        
        print(f"{status:^10} | {path:35} | {description} {result_marker}")
    
    print("-" * 70)
    print()
    
    # 统计
    print("📊 统计结果:")
    print(f"  ✅ 跳过验证: {skip_count} 个文件")
    print(f"  🔒 需要验证: {validate_count} 个文件")
    print(f"  📈 性能提升比例: {skip_count / len(test_cases) * 100:.1f}% 的请求跳过验证")
    print()
    
    # 性能分析
    print("🚀 性能优势:")
    print(f"  - 跳过 IP 白名单检查 (Redis 查询)")
    print(f"  - 跳过路径匹配计算")
    print(f"  - 跳过会话验证逻辑")
    print(f"  - 跳过 HMAC 签名验证")
    print(f"  - 预计性能提升: 20-40%")
    print()


def show_configuration_examples():
    """展示不同的配置示例"""
    print("=" * 70)
    print("配置示例")
    print("=" * 70)
    print()
    
    examples = [
        {
            "name": "最小化配置（仅 HLS）",
            "config": "('.ts',)",
            "description": "仅放行 HLS 视频分片，最保守的配置"
        },
        {
            "name": "HLS + 图片",
            "config": "('.ts', '.webp', '.jpg', '.png')",
            "description": "放行视频分片和常见图片格式"
        },
        {
            "name": "完整静态资源",
            "config": "('.ts', '.webp', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.css', '.js', '.woff', '.woff2', '.ttf')",
            "description": "放行所有常见静态资源，性能最优"
        },
        {
            "name": "当前配置（默认）",
            "config": str(config.FULLY_ALLOWED_EXTENSIONS),
            "description": "向后兼容的默认配置"
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"{i}. {example['name']}")
        print(f"   配置: FULLY_ALLOWED_EXTENSIONS = {example['config']}")
        print(f"   说明: {example['description']}")
        print()


def show_security_recommendations():
    """展示安全建议"""
    print("=" * 70)
    print("⚠️  安全建议")
    print("=" * 70)
    print()
    
    print("✅ 适合放行的文件类型:")
    safe_types = [
        (".ts", "HLS 视频分片（已由 m3u8 验证保护）"),
        (".webp, .jpg, .png", "公开的图片资源"),
        (".css, .js", "前端静态资源"),
        (".woff, .ttf", "字体文件"),
    ]
    for ext, desc in safe_types:
        print(f"  • {ext:20} - {desc}")
    
    print()
    print("❌ 不应放行的文件类型:")
    unsafe_types = [
        (".m3u8", "播放列表文件，需要 HMAC 验证"),
        (".key, enc.key", "加密密钥，必须验证"),
        ("包含用户数据的文件", "可能泄露敏感信息"),
    ]
    for ext, desc in unsafe_types:
        print(f"  • {ext:20} - {desc}")
    
    print()
    print("💡 最佳实践:")
    print("  1. 定期审查配置，移除不需要的扩展名")
    print("  2. 监控放行文件的访问模式")
    print("  3. 在网络层面提供基础保护（防火墙、CDN）")
    print("  4. 对于不确定的文件类型，保持需要验证")
    print()


def main():
    """主函数"""
    try:
        demonstrate_configuration()
        show_configuration_examples()
        show_security_recommendations()
        
        print("=" * 70)
        print("✅ 示例演示完成")
        print("=" * 70)
        print()
        print("更多信息请查看:")
        print("  - 完整文档: docs/FULLY_ALLOWED_EXTENSIONS.md")
        print("  - 快速开始: docs/FULLY_ALLOWED_EXTENSIONS_QUICKSTART.md")
        print("  - 配置文件: models/config.py")
        print()
        
        return 0
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
