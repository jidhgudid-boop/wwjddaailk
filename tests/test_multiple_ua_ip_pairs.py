#!/usr/bin/env python3
"""
测试多UA+IP对功能和静态文件IP-only验证
Test multiple UA+IP pairs per UID and static file IP-only verification
"""
import sys
import os
import json
import asyncio
import hashlib

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.config import config
from services.redis_service import redis_service
from services.auth_service import add_ip_to_whitelist, check_ip_key_path


async def cleanup_test_data(redis_client, uid):
    """清理测试数据"""
    # 清理UID的UA+IP对列表
    await redis_client.delete(f"uid_ua_ip_pairs:{uid}")
    
    # 清理所有可能的ip_cidr_access键
    pattern = "ip_cidr_access:*"
    keys = await redis_client.keys(pattern)
    if keys:
        await redis_client.delete(*keys)
    
    print(f"✅ 清理测试数据完成: uid={uid}")


async def test_multiple_ua_ip_pairs():
    """测试单个UID下多个UA+IP对的管理"""
    print("=" * 60)
    print("测试多UA+IP对功能")
    print("=" * 60)
    
    # 初始化Redis
    await redis_service.initialize(config)
    redis_client = redis_service.get_client()
    
    test_uid = "test_user_123"
    test_path = "/video/abc123/playlist.m3u8"
    test_ips = [
        "192.168.1.100",
        "192.168.2.200",
        "10.0.0.50",
        "172.16.0.100",
        "192.168.3.150",
        "192.168.4.200",  # 第6个，应该触发FIFO删除第1个
    ]
    test_user_agents = [
        "Mozilla/5.0 (Windows NT 10.0) Chrome/120.0",
        "Mozilla/5.0 (iPhone; iOS 17.0) Safari/17.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) Firefox/120.0",
        "Mozilla/5.0 (Linux; Android 13) Chrome/120.0",
        "Mozilla/5.0 (iPad; CPU OS 17_0) Safari/17.0",
        "Mozilla/5.0 (Windows NT 10.0) Edge/120.0",
    ]
    
    try:
        # 清理之前的测试数据
        await cleanup_test_data(redis_client, test_uid)
        
        print(f"\n配置: MAX_UA_IP_PAIRS_PER_UID = {config.MAX_UA_IP_PAIRS_PER_UID}")
        print(f"将添加 {len(test_ips)} 个UA+IP对")
        
        # 添加多个UA+IP对
        results = []
        for i, (ip, ua) in enumerate(zip(test_ips, test_user_agents)):
            print(f"\n--- 添加第 {i+1} 个UA+IP对 ---")
            print(f"IP: {ip}")
            print(f"UA: {ua[:50]}...")
            
            result = await add_ip_to_whitelist(test_uid, test_path, ip, ua)
            results.append(result)
            
            if result.get("success"):
                print(f"✅ 添加成功")
                ua_ip_info = result.get("uid_ua_ip_pairs_info", {})
                print(f"   当前对数: {ua_ip_info.get('current_pairs_count')}")
                print(f"   移除对数: {ua_ip_info.get('pairs_removed')}")
            else:
                print(f"❌ 添加失败: {result.get('error')}")
        
        # 检查最终状态
        print("\n" + "=" * 60)
        print("检查最终状态")
        print("=" * 60)
        
        uid_pairs_key = f"uid_ua_ip_pairs:{test_uid}"
        uid_pairs_data = await redis_client.get(uid_pairs_key)
        
        if uid_pairs_data:
            uid_pairs = json.loads(uid_pairs_data)
            print(f"✅ UID UA+IP对总数: {len(uid_pairs)}")
            print(f"   预期最大数量: {config.MAX_UA_IP_PAIRS_PER_UID}")
            
            assert len(uid_pairs) <= config.MAX_UA_IP_PAIRS_PER_UID, \
                f"UA+IP对数量超过限制: {len(uid_pairs)} > {config.MAX_UA_IP_PAIRS_PER_UID}"
            
            print("\n所有UA+IP对:")
            for idx, pair in enumerate(uid_pairs, 1):
                print(f"  {idx}. pair_id={pair.get('pair_id')}")
                print(f"     ip_pattern={pair.get('ip_pattern')}")
                print(f"     ua_hash={pair.get('ua_hash')}")
            
            # 验证FIFO替换
            if len(test_ips) > config.MAX_UA_IP_PAIRS_PER_UID:
                print(f"\n✅ FIFO替换测试:")
                print(f"   添加了 {len(test_ips)} 个对，保留了最新的 {config.MAX_UA_IP_PAIRS_PER_UID} 个")
                
                # 验证第一个IP应该被移除
                first_ip_pattern = "192.168.1.0/24"
                first_ua_hash = hashlib.md5(test_user_agents[0].encode()).hexdigest()[:8]
                first_pair_id = f"{first_ip_pattern}:{first_ua_hash}"
                
                remaining_pair_ids = [p.get('pair_id') for p in uid_pairs]
                assert first_pair_id not in remaining_pair_ids, \
                    f"最旧的UA+IP对应该被移除: {first_pair_id}"
                print(f"   ✅ 最旧的对已被正确移除")
        else:
            print("❌ 未找到UID UA+IP对数据")
            assert False, "UID UA+IP对数据应该存在"
        
        print("\n✅ 多UA+IP对功能测试通过")
        
    finally:
        # 清理测试数据
        await cleanup_test_data(redis_client, test_uid)
        await redis_service.close()


async def test_static_file_ip_only_check():
    """测试静态文件IP-only验证功能"""
    print("\n" + "=" * 60)
    print("测试静态文件IP-only验证功能")
    print("=" * 60)
    
    # 初始化Redis
    await redis_service.initialize(config)
    redis_client = redis_service.get_client()
    
    test_uid = "test_user_static"
    test_path = "/video/abc123/playlist.m3u8"
    test_ip = "192.168.10.100"
    test_ua = "Mozilla/5.0 (Windows NT 10.0) Chrome/120.0"
    
    try:
        # 清理之前的测试数据
        await cleanup_test_data(redis_client, test_uid)
        
        # 添加IP到白名单
        print(f"\n添加IP到白名单: uid={test_uid}, ip={test_ip}")
        result = await add_ip_to_whitelist(test_uid, test_path, test_ip, test_ua)
        assert result.get("success"), f"添加失败: {result.get('error')}"
        print("✅ 添加成功")
        
        # 保存原始配置
        original_config = config.ENABLE_STATIC_FILE_IP_ONLY_CHECK
        
        # 测试1: 关闭静态文件IP-only验证（默认行为）
        print("\n--- 测试1: 关闭静态文件IP-only验证 ---")
        config.ENABLE_STATIC_FILE_IP_ONLY_CHECK = False
        
        # 静态文件路径（不同的key_path）
        static_path = "/static/images/logo.webp"
        is_allowed, uid = await check_ip_key_path(test_ip, static_path, test_ua)
        print(f"访问静态文件 {static_path}: allowed={is_allowed}")
        assert not is_allowed, "关闭IP-only验证时，不同路径应该被拒绝"
        print("✅ 正确拒绝不同路径的静态文件")
        
        # 测试2: 开启静态文件IP-only验证
        print("\n--- 测试2: 开启静态文件IP-only验证 ---")
        config.ENABLE_STATIC_FILE_IP_ONLY_CHECK = True
        
        # 测试各种静态文件扩展名
        static_files = [
            "/static/images/logo.webp",
            "/assets/photo.jpg",
            "/css/style.css",
            "/fonts/font.woff2",
            "/icons/favicon.ico",
        ]
        
        for static_file in static_files:
            is_allowed, uid = await check_ip_key_path(test_ip, static_file, test_ua)
            print(f"访问 {static_file}: allowed={is_allowed}, uid={uid}")
            assert is_allowed, f"开启IP-only验证时，静态文件应该被允许: {static_file}"
            assert uid == test_uid, f"应该返回正确的UID: {uid}"
        
        print("✅ 所有静态文件都被正确允许")
        
        # 测试3: 非静态文件仍然需要路径验证
        print("\n--- 测试3: 非静态文件仍需路径验证 ---")
        non_static_path = "/video/xyz789/other.m3u8"
        is_allowed, uid = await check_ip_key_path(test_ip, non_static_path, test_ua)
        print(f"访问非静态文件 {non_static_path}: allowed={is_allowed}")
        assert not is_allowed, "非静态文件仍然需要路径验证"
        print("✅ 非静态文件正确进行路径验证")
        
        # 恢复原始配置
        config.ENABLE_STATIC_FILE_IP_ONLY_CHECK = original_config
        
        print("\n✅ 静态文件IP-only验证功能测试通过")
        
    finally:
        # 清理测试数据
        await cleanup_test_data(redis_client, test_uid)
        await redis_service.close()


async def test_config_values():
    """测试配置值"""
    print("\n" + "=" * 60)
    print("测试配置值")
    print("=" * 60)
    
    print(f"MAX_UA_IP_PAIRS_PER_UID: {config.MAX_UA_IP_PAIRS_PER_UID}")
    print(f"ENABLE_STATIC_FILE_IP_ONLY_CHECK: {config.ENABLE_STATIC_FILE_IP_ONLY_CHECK}")
    print(f"STATIC_FILE_EXTENSIONS: {config.STATIC_FILE_EXTENSIONS}")
    
    assert hasattr(config, 'MAX_UA_IP_PAIRS_PER_UID'), "配置缺少 MAX_UA_IP_PAIRS_PER_UID"
    assert hasattr(config, 'ENABLE_STATIC_FILE_IP_ONLY_CHECK'), "配置缺少 ENABLE_STATIC_FILE_IP_ONLY_CHECK"
    assert hasattr(config, 'STATIC_FILE_EXTENSIONS'), "配置缺少 STATIC_FILE_EXTENSIONS"
    
    assert isinstance(config.MAX_UA_IP_PAIRS_PER_UID, int), "MAX_UA_IP_PAIRS_PER_UID应该是整数"
    assert config.MAX_UA_IP_PAIRS_PER_UID > 0, "MAX_UA_IP_PAIRS_PER_UID应该大于0"
    
    print("✅ 所有配置值正确")


async def main():
    """主测试函数"""
    try:
        # 测试配置值
        await test_config_values()
        
        # 测试多UA+IP对功能
        await test_multiple_ua_ip_pairs()
        
        # 测试静态文件IP-only验证
        await test_static_file_ip_only_check()
        
        print("\n" + "=" * 60)
        print("所有测试通过！✅")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
