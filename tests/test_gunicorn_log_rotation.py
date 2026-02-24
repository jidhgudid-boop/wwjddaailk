#!/usr/bin/env python3
"""
集成测试：验证 gunicorn 日志轮转功能
使用实际的 logging 模块来测试轮转是否正常工作
"""
import os
import sys
import tempfile
import shutil
import logging
from logging.config import dictConfig

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from logging_config import logconfig_dict, LOG_MAX_BYTES, LOG_BACKUP_COUNT


def test_gunicorn_logging_config():
    """测试 gunicorn 日志配置可以被正确应用"""
    print("=" * 60)
    print("Gunicorn 日志轮转集成测试")
    print("=" * 60)
    
    # 创建临时目录用于测试
    test_dir = tempfile.mkdtemp()
    
    try:
        # 修改配置使用临时目录
        test_config = dict(logconfig_dict)
        test_config['handlers']['access_file']['filename'] = os.path.join(test_dir, 'access_test.log')
        test_config['handlers']['access_file']['maxBytes'] = 100  # 使用小值以便快速测试
        test_config['handlers']['access_file']['backupCount'] = 3
        test_config['handlers']['error_file']['filename'] = os.path.join(test_dir, 'error_test.log')
        test_config['handlers']['error_file']['maxBytes'] = 100
        test_config['handlers']['error_file']['backupCount'] = 3
        
        # 应用配置
        dictConfig(test_config)
        
        print("\n✓ 日志配置已应用")
        
        # 获取 logger 并写入测试数据
        access_logger = logging.getLogger('gunicorn.access')
        error_logger = logging.getLogger('gunicorn.error')
        
        print("✓ 获取到 access 和 error logger")
        
        # 写入足够多的日志触发轮转
        print("\n写入测试日志以触发轮转...")
        for i in range(30):
            access_logger.info(f"Access log test message {i} - This is a test message to trigger log rotation")
            error_logger.error(f"Error log test message {i} - This is a test message to trigger log rotation")
        
        # 检查文件是否被创建
        files = os.listdir(test_dir)
        print(f"\n创建的日志文件: {', '.join(files)}")
        
        access_files = [f for f in files if f.startswith('access_test.log')]
        error_files = [f for f in files if f.startswith('error_test.log')]
        
        print(f"\n✓ Access 日志文件数: {len(access_files)}")
        print(f"  文件列表: {', '.join(access_files)}")
        
        print(f"\n✓ Error 日志文件数: {len(error_files)}")
        print(f"  文件列表: {', '.join(error_files)}")
        
        # 验证轮转是否发生
        assert len(access_files) >= 2, f"应该至少有 2 个 access 日志文件（主文件 + 备份），实际有 {len(access_files)}"
        assert len(error_files) >= 2, f"应该至少有 2 个 error 日志文件（主文件 + 备份），实际有 {len(error_files)}"
        
        print("\n✅ 日志轮转功能正常工作！")
        
        # 验证原始配置值
        print("\n验证原始配置:")
        print(f"  - LOG_MAX_BYTES: {LOG_MAX_BYTES / 1024 / 1024}MB")
        print(f"  - LOG_BACKUP_COUNT: {LOG_BACKUP_COUNT}")
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过")
        print("=" * 60)
        
    finally:
        # 清理
        shutil.rmtree(test_dir)


if __name__ == '__main__':
    try:
        test_gunicorn_logging_config()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
