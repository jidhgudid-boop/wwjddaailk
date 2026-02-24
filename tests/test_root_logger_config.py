#!/usr/bin/env python3
"""
测试：验证 root logger 配置正确
确保 Gunicorn 日志配置包含 root logger，避免 "Unable to configure root logger" 错误
"""
import os
import sys
import logging
from logging.config import dictConfig

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from logging_config import logconfig_dict


def test_root_logger_configuration():
    """测试 root logger 是否在 logconfig_dict 中正确配置"""
    print("=" * 60)
    print("Root Logger 配置测试")
    print("=" * 60)
    
    # 1. 验证 logconfig_dict 包含 root 配置
    print("\n[1/4] 检查 logconfig_dict 结构...")
    assert 'root' in logconfig_dict, "logconfig_dict 必须包含 'root' 配置"
    print("✓ logconfig_dict 包含 'root' 配置")
    
    # 2. 验证 root 配置的必要字段
    print("\n[2/4] 检查 root 配置字段...")
    root_config = logconfig_dict['root']
    
    assert 'level' in root_config, "root 配置必须包含 'level' 字段"
    print(f"✓ Root logger level: {root_config['level']}")
    
    assert 'handlers' in root_config, "root 配置必须包含 'handlers' 字段"
    assert len(root_config['handlers']) > 0, "root 配置必须至少有一个 handler"
    print(f"✓ Root logger handlers: {root_config['handlers']}")
    
    # 3. 应用配置并验证 root logger
    print("\n[3/4] 应用配置并验证 root logger...")
    dictConfig(logconfig_dict)
    
    root_logger = logging.getLogger()
    print(f"✓ Root logger 已创建")
    print(f"  - Level: {logging.getLevelName(root_logger.level)}")
    print(f"  - Handlers: {len(root_logger.handlers)}")
    
    # 验证 root logger 有 handlers
    assert len(root_logger.handlers) > 0, "Root logger 必须有至少一个 handler"
    print("✓ Root logger 有 handler 可以处理日志")
    
    # 4. 测试 root logger 可以正常工作
    print("\n[4/4] 测试 root logger 功能...")
    
    # 测试不同级别的日志
    test_message = "Test message for root logger"
    
    # 由于 root logger level 是 WARNING，INFO 不应该被记录
    root_logger.info(test_message)
    print("✓ Root logger 接受 INFO 级别消息（可能不会记录）")
    
    # WARNING 应该被记录
    root_logger.warning(f"WARNING: {test_message}")
    print("✓ Root logger 接受 WARNING 级别消息")
    
    # ERROR 应该被记录
    root_logger.error(f"ERROR: {test_message}")
    print("✓ Root logger 接受 ERROR 级别消息")
    
    print("\n" + "=" * 60)
    print("✅ 所有 Root Logger 配置测试通过")
    print("=" * 60)
    print("\n说明:")
    print("  - Root logger 已正确配置")
    print("  - 可以避免 'Unable to configure root logger' 错误")
    print("  - 应用和依赖库的日志消息将被正确处理")
    print("=" * 60)


if __name__ == '__main__':
    try:
        test_root_logger_configuration()
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
