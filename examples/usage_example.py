#!/usr/bin/env python3
"""
使用示例：多UA+IP对管理和静态文件IP-only验证
Usage example for multiple UA+IP pairs and static file IP-only verification
"""

import requests
import json

# 配置
BASE_URL = "http://localhost:7889"
API_KEY = "F2UkWEJZRBxC7"  # 从 config.py 获取

def add_whitelist_entry(uid, path, client_ip, user_agent):
    """添加IP到白名单"""
    url = f"{BASE_URL}/api/whitelist"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "uid": uid,
        "path": path,
        "clientIp": client_ip,
        "UserAgent": user_agent
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return None


def example_multiple_ua_ip_pairs():
    """示例1：添加多个UA+IP对"""
    print("=" * 60)
    print("示例1：添加多个UA+IP对到同一个UID")
    print("=" * 60)
    
    uid = "demo_user_123"
    path = "/video/abc123/playlist.m3u8"
    
    # 模拟用户从不同设备和网络访问
    scenarios = [
        {
            "name": "桌面Chrome浏览器 - 家庭网络",
            "ip": "192.168.1.100",
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"
        },
        {
            "name": "手机Safari浏览器 - 移动网络",
            "ip": "10.20.30.40",
            "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1"
        },
        {
            "name": "平板电脑 - 公司网络",
            "ip": "172.16.50.100",
            "ua": "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1"
        },
        {
            "name": "桌面Firefox浏览器 - 咖啡店WiFi",
            "ip": "192.168.100.50",
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
        }
    ]
    
    print(f"\nUID: {uid}")
    print(f"授权路径: {path}")
    print(f"\n将添加 {len(scenarios)} 个不同的UA+IP组合:\n")
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n--- 添加第 {i} 个UA+IP对 ---")
        print(f"场景: {scenario['name']}")
        print(f"IP: {scenario['ip']}")
        print(f"UA: {scenario['ua'][:60]}...")
        
        result = add_whitelist_entry(uid, path, scenario['ip'], scenario['ua'])
        
        if result and result.get("success"):
            print("✅ 添加成功")
            ua_ip_info = result.get("uid_ua_ip_pairs_info", {})
            print(f"   当前总UA+IP对数: {ua_ip_info.get('current_pairs_count')}")
            print(f"   最大允许数量: {ua_ip_info.get('max_pairs_per_uid')}")
            if ua_ip_info.get('pairs_removed', 0) > 0:
                print(f"   ⚠️  移除了 {ua_ip_info.get('pairs_removed')} 个最旧的对")
        else:
            print(f"❌ 添加失败: {result.get('error') if result else '未知错误'}")
    
    print("\n" + "=" * 60)
    print(f"✅ 示例1完成：用户 {uid} 现在可以从 {len(scenarios)} 个不同的设备/网络访问")
    print("=" * 60)


def example_static_file_access():
    """示例2：静态文件访问"""
    print("\n\n" + "=" * 60)
    print("示例2：静态文件IP-only验证")
    print("=" * 60)
    
    print("\n注意：此示例展示配置概念，实际测试需要：")
    print("1. 在 config.py 中设置: ENABLE_STATIC_FILE_IP_ONLY_CHECK = True")
    print("2. 重启服务器")
    print("3. 使用已授权的IP+UA访问静态文件")
    
    uid = "demo_user_456"
    auth_path = "/video/xyz789/playlist.m3u8"
    test_ip = "192.168.2.100"
    test_ua = "Mozilla/5.0 (Windows NT 10.0) Chrome/120.0"
    
    print(f"\n设置场景:")
    print(f"  UID: {uid}")
    print(f"  授权路径: {auth_path}")
    print(f"  测试IP: {test_ip}")
    
    # 首先添加IP到白名单
    print(f"\n步骤1: 添加IP到白名单")
    result = add_whitelist_entry(uid, auth_path, test_ip, test_ua)
    if result and result.get("success"):
        print("✅ 白名单添加成功")
    else:
        print("❌ 白名单添加失败")
        return
    
    print(f"\n步骤2: 访问测试")
    print("\n当 ENABLE_STATIC_FILE_IP_ONLY_CHECK = False (默认):")
    print("  ✅ GET /video/xyz789/playlist.m3u8   - 允许（路径匹配）")
    print("  ✅ GET /video/xyz789/logo.webp       - 允许（路径匹配）")
    print("  ❌ GET /static/images/logo.webp      - 拒绝（路径不匹配）")
    print("  ❌ GET /assets/photo.jpg             - 拒绝（路径不匹配）")
    
    print("\n当 ENABLE_STATIC_FILE_IP_ONLY_CHECK = True:")
    print("  ✅ GET /video/xyz789/playlist.m3u8   - 允许（路径匹配）")
    print("  ✅ GET /video/xyz789/logo.webp       - 允许（静态文件+IP验证）")
    print("  ✅ GET /static/images/logo.webp      - 允许（静态文件+IP验证）")
    print("  ✅ GET /assets/photo.jpg             - 允许（静态文件+IP验证）")
    print("  ❌ GET /other/video/file.m3u8        - 拒绝（非静态，路径不匹配）")
    
    print("\n" + "=" * 60)
    print("✅ 示例2完成：静态文件IP-only验证功能说明")
    print("=" * 60)


def example_fifo_replacement():
    """示例3：FIFO替换演示"""
    print("\n\n" + "=" * 60)
    print("示例3：FIFO替换机制演示")
    print("=" * 60)
    
    uid = "demo_user_789"
    path = "/video/demo/playlist.m3u8"
    
    # 添加超过限制的UA+IP对（假设MAX_UA_IP_PAIRS_PER_UID=5）
    print("\n配置: MAX_UA_IP_PAIRS_PER_UID = 5")
    print("将添加 7 个UA+IP对，预期最旧的2个会被自动删除\n")
    
    devices = [
        ("192.168.1.10", "Device 1 - Chrome Desktop"),
        ("192.168.1.20", "Device 2 - Safari Mobile"),
        ("192.168.1.30", "Device 3 - Firefox Desktop"),
        ("192.168.1.40", "Device 4 - Chrome Mobile"),
        ("192.168.1.50", "Device 5 - Edge Desktop"),
        ("192.168.1.60", "Device 6 - Opera Desktop"),  # 第6个，应该删除第1个
        ("192.168.1.70", "Device 7 - Brave Desktop"),  # 第7个，应该删除第2个
    ]
    
    for i, (ip, device) in enumerate(devices, 1):
        print(f"\n添加第 {i} 个: {device} ({ip})")
        ua = f"Mozilla/5.0 ({device})"
        
        result = add_whitelist_entry(uid, path, ip, ua)
        
        if result and result.get("success"):
            ua_ip_info = result.get("uid_ua_ip_pairs_info", {})
            current = ua_ip_info.get('current_pairs_count', 0)
            removed = ua_ip_info.get('pairs_removed', 0)
            
            print(f"  当前对数: {current}")
            if removed > 0:
                print(f"  ⚠️  自动删除了 {removed} 个最旧的对")
    
    print("\n" + "=" * 60)
    print("✅ 示例3完成：FIFO替换自动管理UA+IP对数量")
    print("=" * 60)


def main():
    """主函数"""
    print("\n")
    print("*" * 60)
    print("FileProxy 新功能使用示例")
    print("多UA+IP对管理 & 静态文件IP-only验证")
    print("*" * 60)
    
    print("\n提示：")
    print("1. 确保FileProxy服务器运行在 http://localhost:7889")
    print("2. API_KEY 需要与 config.py 中的 API_KEY 匹配")
    print("3. 这些示例会调用真实的API endpoint")
    
    response = input("\n是否继续？(y/n): ")
    if response.lower() != 'y':
        print("已取消")
        return
    
    try:
        # 运行示例
        example_multiple_ua_ip_pairs()
        example_static_file_access()
        example_fifo_replacement()
        
        print("\n\n" + "*" * 60)
        print("所有示例完成！")
        print("*" * 60)
        print("\n查看更多信息：")
        print("  文档: docs/MULTI_UA_IP_PAIRS.md")
        print("  测试: python tests/test_ua_ip_pairs_unit.py")
        
    except KeyboardInterrupt:
        print("\n\n已中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
