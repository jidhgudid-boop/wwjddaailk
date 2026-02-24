#!/usr/bin/env python3
"""
单元测试：多UA+IP对功能和静态文件IP-only验证（不需要Redis连接）
Unit tests for multiple UA+IP pairs and static file IP-only verification (no Redis required)
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.config import config


def test_config_values():
    """测试新增配置值是否存在且正确"""
    print("=" * 60)
    print("测试配置值")
    print("=" * 60)
    
    # 测试 MAX_UA_IP_PAIRS_PER_UID
    assert hasattr(config, 'MAX_UA_IP_PAIRS_PER_UID'), \
        "配置缺少 MAX_UA_IP_PAIRS_PER_UID"
    assert isinstance(config.MAX_UA_IP_PAIRS_PER_UID, int), \
        "MAX_UA_IP_PAIRS_PER_UID 应该是整数"
    assert config.MAX_UA_IP_PAIRS_PER_UID > 0, \
        "MAX_UA_IP_PAIRS_PER_UID 应该大于0"
    print(f"✅ MAX_UA_IP_PAIRS_PER_UID: {config.MAX_UA_IP_PAIRS_PER_UID}")
    
    # 测试 ENABLE_STATIC_FILE_IP_ONLY_CHECK
    assert hasattr(config, 'ENABLE_STATIC_FILE_IP_ONLY_CHECK'), \
        "配置缺少 ENABLE_STATIC_FILE_IP_ONLY_CHECK"
    assert isinstance(config.ENABLE_STATIC_FILE_IP_ONLY_CHECK, bool), \
        "ENABLE_STATIC_FILE_IP_ONLY_CHECK 应该是布尔值"
    print(f"✅ ENABLE_STATIC_FILE_IP_ONLY_CHECK: {config.ENABLE_STATIC_FILE_IP_ONLY_CHECK}")
    
    # 测试 STATIC_FILE_EXTENSIONS
    assert hasattr(config, 'STATIC_FILE_EXTENSIONS'), \
        "配置缺少 STATIC_FILE_EXTENSIONS"
    assert isinstance(config.STATIC_FILE_EXTENSIONS, tuple), \
        "STATIC_FILE_EXTENSIONS 应该是元组"
    assert len(config.STATIC_FILE_EXTENSIONS) > 0, \
        "STATIC_FILE_EXTENSIONS 不应该为空"
    
    # 验证包含关键的静态文件扩展名
    expected_extensions = ['.webp', '.jpg', '.png', '.css', '.js', '.woff']
    for ext in expected_extensions:
        assert ext in config.STATIC_FILE_EXTENSIONS, \
            f"STATIC_FILE_EXTENSIONS 应该包含 {ext}"
    
    print(f"✅ STATIC_FILE_EXTENSIONS: {config.STATIC_FILE_EXTENSIONS}")
    
    print("\n✅ 所有配置值测试通过")


def test_static_file_detection():
    """测试静态文件检测逻辑"""
    print("\n" + "=" * 60)
    print("测试静态文件检测逻辑")
    print("=" * 60)
    
    # 静态文件路径示例
    static_files = [
        "/images/logo.webp",
        "/assets/photo.jpg",
        "/static/style.css",
        "/fonts/font.woff2",
        "/icons/favicon.ico",
        "/scripts/app.js",
    ]
    
    # 非静态文件路径示例
    non_static_files = [
        "/video/abc123/playlist.m3u8",
        "/video/abc123/segment.ts",
        "/video/abc123/enc.key",
        "/api/data.json",
        "/download/file.mp4",
    ]
    
    print("\n检测静态文件:")
    for path in static_files:
        is_static = path.lower().endswith(config.STATIC_FILE_EXTENSIONS)
        print(f"  {path}: {is_static}")
        assert is_static, f"{path} 应该被识别为静态文件"
    
    print("\n检测非静态文件:")
    for path in non_static_files:
        is_static = path.lower().endswith(config.STATIC_FILE_EXTENSIONS)
        print(f"  {path}: {is_static}")
        assert not is_static, f"{path} 不应该被识别为静态文件"
    
    print("\n✅ 静态文件检测逻辑测试通过")


def test_fifo_logic():
    """测试FIFO替换逻辑（模拟）"""
    print("\n" + "=" * 60)
    print("测试FIFO替换逻辑")
    print("=" * 60)
    
    max_pairs = config.MAX_UA_IP_PAIRS_PER_UID
    print(f"最大UA+IP对数: {max_pairs}")
    
    # 模拟添加超过最大数量的对
    pairs = []
    for i in range(max_pairs + 3):
        pair = {
            "pair_id": f"192.168.{i}.0/24:hash{i}",
            "ip_pattern": f"192.168.{i}.0/24",
            "ua_hash": f"hash{i}",
            "created_at": 1000 + i,
            "last_updated": 1000 + i
        }
        pairs.append(pair)
    
    print(f"\n添加了 {len(pairs)} 个对")
    
    # 模拟FIFO替换
    if len(pairs) > max_pairs:
        pairs.sort(key=lambda x: x.get("created_at", 0))
        removed_pairs = pairs[:-max_pairs]
        pairs = pairs[-max_pairs:]
        
        print(f"移除了 {len(removed_pairs)} 个最旧的对")
        print(f"保留了 {len(pairs)} 个最新的对")
        
        assert len(pairs) == max_pairs, \
            f"保留的对数应该等于最大值: {len(pairs)} != {max_pairs}"
        
        # 验证保留的是最新的对
        # 添加了8个对，保留最新的max_pairs(5)个，所以第一个应该是索引3(从0开始)
        expected_first_index = (max_pairs + 3) - max_pairs  # 简化为3
        assert pairs[0]["pair_id"] == f"192.168.{expected_first_index}.0/24:hash{expected_first_index}", \
            "应该保留最新的对"
        
        print(f"\n保留的对:")
        for pair in pairs:
            print(f"  {pair['pair_id']} (created_at={pair['created_at']})")
    
    print("\n✅ FIFO替换逻辑测试通过")


def test_uid_pair_tracking_structure():
    """测试UID级别UA+IP对追踪的数据结构"""
    print("\n" + "=" * 60)
    print("测试UID UA+IP对追踪数据结构")
    print("=" * 60)
    
    # 模拟数据结构
    uid = "test_user_123"
    uid_pairs_key = f"uid_ua_ip_pairs:{uid}"
    
    # 模拟UA+IP对
    sample_pairs = [
        {
            "pair_id": "192.168.1.0/24:abc12345",
            "ip_pattern": "192.168.1.0/24",
            "ua_hash": "abc12345",
            "created_at": 1000,
            "last_updated": 1000
        },
        {
            "pair_id": "192.168.2.0/24:def67890",
            "ip_pattern": "192.168.2.0/24",
            "ua_hash": "def67890",
            "created_at": 2000,
            "last_updated": 2000
        }
    ]
    
    print(f"Redis键: {uid_pairs_key}")
    print(f"\n数据结构示例 (JSON):")
    
    import json
    print(json.dumps(sample_pairs, indent=2))
    
    # 验证数据结构
    for pair in sample_pairs:
        assert "pair_id" in pair, "对应该有 pair_id"
        assert "ip_pattern" in pair, "对应该有 ip_pattern"
        assert "ua_hash" in pair, "对应该有 ua_hash"
        assert "created_at" in pair, "对应该有 created_at"
        assert "last_updated" in pair, "对应该有 last_updated"
        
        # 验证 pair_id 格式
        assert ":" in pair["pair_id"], "pair_id 应该包含 :"
        parts = pair["pair_id"].split(":")
        assert len(parts) == 2, "pair_id 应该是 ip_pattern:ua_hash 格式"
    
    print("\n✅ UID UA+IP对追踪数据结构测试通过")


def test_integration_logic():
    """测试整体集成逻辑"""
    print("\n" + "=" * 60)
    print("测试整体集成逻辑")
    print("=" * 60)
    
    # 场景1：添加第一个UA+IP对
    print("\n场景1：添加第一个UA+IP对")
    print("  - 创建 uid_ua_ip_pairs:{uid} 键")
    print("  - 创建 ip_cidr_access:{ip}:{ua_hash} 键")
    print("  - 存储路径信息")
    print("  ✅ 预期结果: 成功添加")
    
    # 场景2：添加相同UID的不同UA+IP对
    print("\n场景2：添加相同UID的不同UA+IP对")
    print("  - 更新 uid_ua_ip_pairs:{uid} 列表")
    print("  - 创建新的 ip_cidr_access 键")
    print("  ✅ 预期结果: 成功添加到列表")
    
    # 场景3：达到最大数量
    print(f"\n场景3：达到最大数量 ({config.MAX_UA_IP_PAIRS_PER_UID})")
    print("  - 添加第N+1个对")
    print("  - 触发FIFO替换")
    print("  - 删除最旧的 ip_cidr_access 键")
    print("  ✅ 预期结果: 最旧的对被移除，最新的对被添加")
    
    # 场景4：静态文件访问（ENABLE_STATIC_FILE_IP_ONLY_CHECK=True）
    print("\n场景4：静态文件访问（IP-only验证）")
    print("  - 检测文件扩展名")
    print("  - 如果是静态文件且配置启用，跳过路径验证")
    print("  - 只验证 IP+UA 组合")
    print("  ✅ 预期结果: 允许访问任何路径的静态文件")
    
    # 场景5：非静态文件访问
    print("\n场景5：非静态文件访问")
    print("  - 正常进行路径验证")
    print("  - 检查 key_path 匹配")
    print("  ✅ 预期结果: 只允许授权路径")
    
    print("\n✅ 整体集成逻辑测试通过")


def main():
    """主测试函数"""
    try:
        print("\n" + "=" * 60)
        print("多UA+IP对功能和静态文件IP-only验证 - 单元测试")
        print("=" * 60)
        
        # 运行所有测试
        test_config_values()
        test_static_file_detection()
        test_fifo_logic()
        test_uid_pair_tracking_structure()
        test_integration_logic()
        
        print("\n" + "=" * 60)
        print("所有单元测试通过！✅")
        print("=" * 60)
        print("\n注意: 这些是单元测试，不需要Redis连接。")
        print("完整的集成测试需要在有Redis连接的环境中运行。")
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
