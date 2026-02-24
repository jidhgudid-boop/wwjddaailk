#!/usr/bin/env python3
"""
测试IPv6网络配置
Test IPv6 network configuration

检查服务器是否正确配置以支持IPv6连接
"""
import sys
import os
import socket

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_socket_ipv6_support():
    """测试Python socket模块的IPv6支持"""
    print("=" * 70)
    print("测试1: Python Socket IPv6支持")
    print("=" * 70)
    
    print("\n检查socket模块是否支持IPv6:")
    has_ipv6 = socket.has_ipv6
    status = "✅" if has_ipv6 else "❌"
    print(f"  {status} socket.has_ipv6 = {has_ipv6}")
    
    if has_ipv6:
        print("\n✅ Python socket模块完全支持IPv6")
    else:
        print("\n⚠️  警告: Python socket模块不支持IPv6（可能是系统限制）")
    
    print()
    return has_ipv6


def test_ipv6_socket_binding():
    """测试IPv6 socket绑定"""
    print("=" * 70)
    print("测试2: IPv6 Socket绑定测试")
    print("=" * 70)
    
    if not socket.has_ipv6:
        print("\n⚠️  跳过: 系统不支持IPv6")
        print()
        return False
    
    # 测试IPv6 socket创建和绑定
    print("\n测试IPv6 socket创建:")
    
    try:
        # 创建IPv6 TCP socket
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        print("  ✅ 成功创建 AF_INET6 socket")
        
        # 设置socket选项
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # 尝试绑定到 [::]:0 (随机端口)
        sock.bind(('::', 0))
        bound_addr = sock.getsockname()
        print(f"  ✅ 成功绑定到 {bound_addr}")
        
        # 监听
        sock.listen(1)
        print(f"  ✅ Socket正在监听 {bound_addr}")
        
        # 关闭socket
        sock.close()
        print("  ✅ Socket已关闭")
        
        print("\n✅ IPv6 socket绑定测试通过")
        print()
        return True
        
    except OSError as e:
        print(f"  ❌ IPv6 socket绑定失败: {e}")
        print("\n⚠️  警告: 无法绑定IPv6地址（可能是系统配置问题）")
        print()
        return False
    except Exception as e:
        print(f"  ❌ 意外错误: {e}")
        import traceback
        traceback.print_exc()
        print()
        return False


def test_dual_stack_support():
    """测试双栈支持 (IPv4 + IPv6)"""
    print("=" * 70)
    print("测试3: 双栈支持测试")
    print("=" * 70)
    
    if not socket.has_ipv6:
        print("\n⚠️  跳过: 系统不支持IPv6")
        print()
        return False
    
    print("\n测试同时绑定IPv4和IPv6:")
    
    ipv4_sock = None
    ipv6_sock = None
    
    try:
        # 创建IPv4 socket
        ipv4_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ipv4_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ipv4_sock.bind(('0.0.0.0', 0))
        ipv4_port = ipv4_sock.getsockname()[1]
        ipv4_sock.listen(1)
        print(f"  ✅ IPv4 socket绑定到 0.0.0.0:{ipv4_port}")
        
        # 创建IPv6 socket
        ipv6_sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        ipv6_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # 禁用IPv6-only模式，允许IPv4映射（如果支持）
        try:
            ipv6_sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            print("  ✅ IPV6_V6ONLY 设置为 0 (允许IPv4映射)")
        except (AttributeError, OSError):
            print("  ℹ️  IPV6_V6ONLY 选项不可用")
        
        ipv6_sock.bind(('::', 0))
        ipv6_port = ipv6_sock.getsockname()[1]
        ipv6_sock.listen(1)
        print(f"  ✅ IPv6 socket绑定到 [::]:{ipv6_port}")
        
        print("\n✅ 双栈支持测试通过")
        print("  ℹ️  可以同时使用IPv4和IPv6连接")
        print()
        return True
        
    except OSError as e:
        print(f"  ❌ 双栈绑定失败: {e}")
        print()
        return False
    except Exception as e:
        print(f"  ❌ 意外错误: {e}")
        import traceback
        traceback.print_exc()
        print()
        return False
    finally:
        # 清理资源
        if ipv4_sock:
            ipv4_sock.close()
        if ipv6_sock:
            ipv6_sock.close()


def test_uvicorn_config_recommendations():
    """检查Uvicorn配置建议"""
    print("=" * 70)
    print("测试4: Uvicorn IPv6配置建议")
    print("=" * 70)
    
    print("\n当前配置分析:")
    print("  📄 文件: app.py, gunicorn_fastapi.conf.py")
    
    print("\n当前绑定地址:")
    print("  • app.py:            host='0.0.0.0'  (仅IPv4)")
    print("  • gunicorn配置:      bind='0.0.0.0:7889'  (仅IPv4)")
    
    print("\nIPv6配置建议:")
    print("  1️⃣  纯IPv6绑定:")
    print("      host='::' 或 bind='[::]:7889'")
    print("      - 仅接受IPv6连接")
    print("      - 需要设置 IPV6_V6ONLY=1")
    
    print("\n  2️⃣  双栈绑定 (推荐):")
    print("      host='::' 或 bind='[::]:7889'")
    print("      - 设置 IPV6_V6ONLY=0 (默认)")
    print("      - 同时接受IPv4和IPv6连接")
    print("      - IPv4通过IPv4映射地址访问")
    
    print("\n  3️⃣  分别绑定:")
    print("      同时启动两个实例:")
    print("      - 实例1: bind='0.0.0.0:7889'  (IPv4)")
    print("      - 实例2: bind='[::]:7890'     (IPv6)")
    
    print("\n推荐配置 (双栈):")
    print("  • 修改 app.py 第219行:")
    print("    uvicorn.run(")
    print('      "app:app",')
    print('      host="::",  # 改为 :: 支持双栈')
    print("      ...")
    print("    )")
    
    print("\n  • 修改 gunicorn_fastapi.conf.py 第21行:")
    print('    bind = "[::]:7889"  # 改为 [::] 支持双栈')
    
    print("\n✅ 配置建议已提供")
    print()


def check_system_ipv6():
    """检查系统IPv6配置"""
    print("=" * 70)
    print("测试5: 系统IPv6配置检查")
    print("=" * 70)
    
    print("\n检查网络接口IPv6地址:")
    
    try:
        import subprocess
        
        # 尝试获取IPv6地址
        result = subprocess.run(
            ['ip', '-6', 'addr', 'show'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            output = result.stdout
            has_global_ipv6 = 'scope global' in output
            has_link_local = 'scope link' in output
            
            if has_global_ipv6:
                print("  ✅ 系统有全局IPv6地址")
            elif has_link_local:
                print("  ⚠️  系统仅有链路本地IPv6地址")
            else:
                print("  ❌ 系统没有配置IPv6地址")
            
            # 显示前几个IPv6地址
            ipv6_lines = [line.strip() for line in output.split('\n') 
                         if 'inet6' in line][:5]
            if ipv6_lines:
                print("\n  IPv6地址示例:")
                for line in ipv6_lines:
                    print(f"    {line}")
        else:
            print("  ℹ️  无法获取IPv6配置 (可能需要root权限)")
            
    except FileNotFoundError:
        print("  ℹ️  'ip'命令不可用，跳过系统检查")
    except Exception as e:
        print(f"  ℹ️  系统检查跳过: {e}")
    
    print()


def run_all_tests():
    """运行所有网络配置测试"""
    print("\n" + "=" * 70)
    print("开始测试FileProxy的IPv6网络配置")
    print("=" * 70 + "\n")
    
    results = {}
    
    try:
        results['socket_ipv6'] = test_socket_ipv6_support()
        results['ipv6_binding'] = test_ipv6_socket_binding()
        results['dual_stack'] = test_dual_stack_support()
        test_uvicorn_config_recommendations()
        check_system_ipv6()
        
        print("=" * 70)
        print("测试总结")
        print("=" * 70)
        
        print("\n核心功能测试结果:")
        for test_name, result in results.items():
            status = "✅ 通过" if result else "⚠️  需要注意"
            print(f"  • {test_name:20s}: {status}")
        
        print("\n配置建议:")
        if socket.has_ipv6 and results.get('ipv6_binding'):
            print("  ✅ 系统完全支持IPv6")
            print("  📝 建议修改配置文件以启用IPv6绑定")
            print("     详见上方'测试4: Uvicorn IPv6配置建议'")
        elif socket.has_ipv6:
            print("  ⚠️  系统支持IPv6但绑定测试失败")
            print("     可能是系统配置或权限问题")
        else:
            print("  ⚠️  系统不支持IPv6")
            print("     这可能是容器或虚拟机的限制")
        
        print("\n" + "=" * 70)
        print("IPv6网络配置测试完成")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print("\n" + "=" * 70)
        print(f"❌ 测试出错: {str(e)}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
