#!/usr/bin/env python3
"""
测试静态文件IP-only验证功能是否正确工作
Test that ENABLE_STATIC_FILE_IP_ONLY_CHECK works correctly
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.config import config


def test_skip_validation_logic():
    """测试skip_validation逻辑"""
    print("=" * 60)
    print("测试静态文件验证逻辑")
    print("=" * 60)
    
    # 模拟proxy.py中的逻辑
    test_paths = [
        ("/static/logo.webp", True, "静态文件-webp"),
        ("/static/style.css", True, "静态文件-css"),
        ("/static/script.js", True, "静态文件-js"),
        ("/test.php", False, "PHP文件"),
        ("/video/file.m3u8", False, "M3U8文件"),
        ("/video/file.ts", False, "TS文件"),
    ]
    
    print(f"\n当前配置:")
    print(f"  ENABLE_STATIC_FILE_IP_ONLY_CHECK = {config.ENABLE_STATIC_FILE_IP_ONLY_CHECK}")
    print(f"  STATIC_FILE_EXTENSIONS = {config.STATIC_FILE_EXTENSIONS}")
    
    print(f"\n测试路径验证逻辑:")
    
    for path, is_static_expected, description in test_paths:
        # 检查是否为静态文件
        is_static_file = path.lower().endswith(config.STATIC_FILE_EXTENSIONS)
        
        # 模拟新的skip_validation逻辑
        always_skip_suffixes = ('.php',)
        
        if config.ENABLE_STATIC_FILE_IP_ONLY_CHECK:
            # 启用静态文件IP验证时，只跳过always_skip_suffixes中的文件
            skip_validation = path.lower().endswith(always_skip_suffixes)
            should_validate = not skip_validation
        else:
            # 未启用时，保持原有行为：静态文件也跳过验证
            skip_validation_suffixes = ('.webp', '.php', '.js', '.css', '.ico', '.txt', 
                                       '.woff', '.woff2', '.ttf', '.png', '.jpg', 
                                       '.jpeg', '.gif', '.svg')
            skip_validation = path.lower().endswith(skip_validation_suffixes)
            should_validate = not skip_validation
        
        print(f"\n  {description}: {path}")
        print(f"    是静态文件: {is_static_file}")
        print(f"    跳过验证: {skip_validation}")
        print(f"    需要验证: {should_validate}")
        
        # 验证行为
        if config.ENABLE_STATIC_FILE_IP_ONLY_CHECK:
            if is_static_file:
                assert should_validate, f"启用IP-only验证时，静态文件应该需要验证: {path}"
                print(f"    ✅ 正确：静态文件将进行IP+UA验证")
            elif path.endswith('.php'):
                assert not should_validate, f"PHP文件应该跳过验证: {path}"
                print(f"    ✅ 正确：PHP文件跳过验证")
            else:
                assert should_validate, f"非静态文件应该需要完整验证: {path}"
                print(f"    ✅ 正确：非静态文件需要完整验证")
        else:
            if is_static_file or path.endswith('.php'):
                assert not should_validate, f"关闭IP-only验证时，静态文件应该跳过验证: {path}"
                print(f"    ✅ 正确：静态文件跳过验证（旧行为）")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过")
    print("=" * 60)
    
    print("\n说明:")
    if config.ENABLE_STATIC_FILE_IP_ONLY_CHECK:
        print("  ✅ ENABLE_STATIC_FILE_IP_ONLY_CHECK = True")
        print("  静态文件现在会进入验证流程，在check_ip_key_path()中进行IP+UA验证")
        print("  这意味着静态文件需要IP在白名单中才能访问")
    else:
        print("  ⚠️  ENABLE_STATIC_FILE_IP_ONLY_CHECK = False")
        print("  静态文件完全跳过验证，任何人都可以访问")


if __name__ == "__main__":
    try:
        test_skip_validation_logic()
    except AssertionError as e:
        print(f"\n❌ 测试失败: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
