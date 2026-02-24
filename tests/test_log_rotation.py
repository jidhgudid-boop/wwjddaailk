#!/usr/bin/env python3
"""
测试日志轮转配置
验证 RotatingFileHandler 是否正确配置
"""
import os
import sys
import tempfile
import shutil
from logging.handlers import RotatingFileHandler
import logging

# 添加父目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from logging_config import logconfig_dict, LOG_MAX_BYTES, LOG_BACKUP_COUNT


def test_logconfig_dict_structure():
    """测试日志配置字典结构"""
    print("测试 1: 验证日志配置字典结构...")
    
    assert 'version' in logconfig_dict
    assert logconfig_dict['version'] == 1
    
    assert 'handlers' in logconfig_dict
    assert 'access_file' in logconfig_dict['handlers']
    assert 'error_file' in logconfig_dict['handlers']
    
    print("✓ 日志配置字典结构正确")


def test_rotating_handler_config():
    """测试 RotatingFileHandler 配置"""
    print("\n测试 2: 验证 RotatingFileHandler 配置...")
    
    access_handler = logconfig_dict['handlers']['access_file']
    error_handler = logconfig_dict['handlers']['error_file']
    
    # 验证类型
    assert access_handler['class'] == 'logging.handlers.RotatingFileHandler'
    assert error_handler['class'] == 'logging.handlers.RotatingFileHandler'
    
    # 验证最大字节数（8MB）
    assert access_handler['maxBytes'] == 8 * 1024 * 1024
    assert error_handler['maxBytes'] == 8 * 1024 * 1024
    
    # 验证备份数量（10）
    assert access_handler['backupCount'] == 10
    assert error_handler['backupCount'] == 10
    
    print(f"✓ 最大文件大小: {access_handler['maxBytes'] / 1024 / 1024}MB")
    print(f"✓ 备份文件数量: {access_handler['backupCount']}")
    print("✓ RotatingFileHandler 配置正确")


def test_log_rotation_functionality():
    """测试日志轮转功能"""
    print("\n测试 3: 验证日志轮转功能...")
    
    # 创建临时目录
    test_dir = tempfile.mkdtemp()
    test_log_file = os.path.join(test_dir, "test_rotation.log")
    
    try:
        # 创建一个小的日志文件用于测试（100 bytes）
        handler = RotatingFileHandler(
            test_log_file,
            maxBytes=100,  # 很小的大小用于快速测试
            backupCount=3,
            encoding='utf-8'
        )
        
        logger = logging.getLogger('test_rotation')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # 写入足够多的日志来触发轮转
        for i in range(20):
            logger.info(f"Test log message {i} - This is a longer message to trigger rotation")
        
        handler.close()
        logger.removeHandler(handler)
        
        # 检查是否创建了备份文件
        log_files = [f for f in os.listdir(test_dir) if f.startswith('test_rotation.log')]
        
        print(f"✓ 创建了 {len(log_files)} 个日志文件（含主文件）")
        
        # 应该有主文件和至少一个备份文件
        assert len(log_files) >= 2, "应该创建了备份文件"
        
        # 检查备份文件
        backup_files = [f for f in log_files if f != 'test_rotation.log']
        print(f"✓ 备份文件: {', '.join(backup_files)}")
        
        print("✓ 日志轮转功能正常工作")
        
    finally:
        # 清理临时目录
        shutil.rmtree(test_dir)


def test_constants():
    """测试常量配置"""
    print("\n测试 4: 验证常量配置...")
    
    assert LOG_MAX_BYTES == 8 * 1024 * 1024, "LOG_MAX_BYTES 应该是 8MB"
    assert LOG_BACKUP_COUNT == 10, "LOG_BACKUP_COUNT 应该是 10"
    
    print(f"✓ LOG_MAX_BYTES = {LOG_MAX_BYTES / 1024 / 1024}MB")
    print(f"✓ LOG_BACKUP_COUNT = {LOG_BACKUP_COUNT}")


def test_log_file_paths():
    """测试日志文件路径"""
    print("\n测试 5: 验证日志文件路径...")
    
    access_log = logconfig_dict['handlers']['access_file']['filename']
    error_log = logconfig_dict['handlers']['error_file']['filename']
    
    print(f"✓ Access log: {access_log}")
    print(f"✓ Error log: {error_log}")
    
    # 验证文件名
    assert access_log.endswith('access_fastapi.log')
    assert error_log.endswith('error_fastapi.log')
    
    print("✓ 日志文件路径配置正确")


if __name__ == '__main__':
    print("=" * 60)
    print("日志轮转配置测试")
    print("=" * 60)
    
    try:
        test_logconfig_dict_structure()
        test_rotating_handler_config()
        test_log_rotation_functionality()
        test_constants()
        test_log_file_paths()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        print("\n配置摘要:")
        print(f"  - 每个日志文件最大: 8MB")
        print(f"  - 最多保留备份: 10 份")
        print(f"  - 总计最大日志空间: ~88MB (8MB × 11 文件)")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
