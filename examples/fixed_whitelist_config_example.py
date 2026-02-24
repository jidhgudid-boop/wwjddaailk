#!/usr/bin/env python3
"""
固定白名单配置示例
Example configuration for fixed IP whitelist

此文件展示了如何在 config.py 中配置固定白名单
This file shows how to configure fixed whitelist in config.py
"""

# 示例 1: 空白名单（默认）
# Example 1: Empty whitelist (default)
FIXED_IP_WHITELIST = []

# 示例 2: 单个IP
# Example 2: Single IP
# FIXED_IP_WHITELIST = ["192.168.1.100"]

# 示例 3: 多个单独的IP
# Example 3: Multiple individual IPs
# FIXED_IP_WHITELIST = [
#     "192.168.1.100",
#     "192.168.1.101",
#     "10.0.0.1"
# ]

# 示例 4: CIDR范围
# Example 4: CIDR range
# FIXED_IP_WHITELIST = ["192.168.1.0/24"]

# 示例 5: 混合配置（推荐用于生产环境）
# Example 5: Mixed configuration (recommended for production)
# FIXED_IP_WHITELIST = [
#     # 内部网络 / Internal network
#     "10.0.0.0/8",
#     "172.16.0.0/12",
#     "192.168.0.0/16",
#     
#     # IPv6 内部网络 / IPv6 Internal network
#     "fd00::/8",            # 唯一本地地址 / Unique Local Addresses
#     "2001:db8::/32",       # 文档示例（替换为实际网络）/ Doc example (replace with actual)
#     
#     # 管理IP / Admin IPs
#     "203.0.113.10",
#     "203.0.113.11",
#     "2001:db8:1::10",      # IPv6 管理IP / IPv6 Admin IP
#     
#     # 本地开发 / Local development
#     "127.0.0.1",           # IPv4 本地 / IPv4 Local
#     "::1",                 # IPv6 本地 / IPv6 Local
# ]

# 示例 6: 开发环境配置
# Example 6: Development environment
# FIXED_IP_WHITELIST = [
#     "127.0.0.1",           # IPv4 本地 / IPv4 Local
#     "::1",                 # IPv6 本地 / IPv6 Local
#     "192.168.1.0/24",      # IPv4 开发网络 / IPv4 Dev network
#     "fe80::/64"            # IPv6 链路本地 / IPv6 Link-local
# ]

# 示例 7: 生产环境配置
# Example 7: Production environment
# FIXED_IP_WHITELIST = [
#     # IPv4 网段 / IPv4 subnets
#     "10.0.1.0/24",         # 应用服务器网段 / App server subnet
#     "10.0.2.10",           # 监控服务器 / Monitoring server
#     "10.0.2.11",           # 备份服务器 / Backup server
#     
#     # IPv6 网段 / IPv6 subnets
#     "2001:db8:1::/64",     # 应用服务器网段 / App server subnet
#     "2001:db8:2::10",      # 监控服务器 / Monitoring server
# ]

# 示例 8: 纯IPv6环境配置
# Example 8: IPv6-only environment
# FIXED_IP_WHITELIST = [
#     "2001:db8::/32",       # 组织网络 / Organization network
#     "2001:db8:1::/64",     # 应用子网 / Application subnet
#     "fe80::/10",           # 链路本地地址 / Link-local addresses
#     "::1",                 # 本地回环 / Loopback
# ]

# 使用说明 / Usage instructions:
# 1. 将需要的配置取消注释 / Uncomment the configuration you need
# 2. 修改IP地址以匹配你的环境 / Modify IP addresses to match your environment
# 3. 将配置复制到 models/config.py 中的 Config 类 / Copy configuration to Config class in models/config.py
# 4. 重启服务器使配置生效 / Restart server to apply changes

# 安全提示 / Security notes:
# - 仅添加可信任的IP / Only add trusted IPs
# - 避免使用过大的CIDR范围 / Avoid using too large CIDR ranges
# - 定期审查白名单配置 / Review whitelist configuration regularly
# - 不要添加 0.0.0.0/0 或 ::/0 (允许所有IP) / Do not add 0.0.0.0/0 or ::/0 (allows all IPs)

# IPv6 地址格式说明 / IPv6 address format notes:
# - 完整格式: 2001:0db8:85a3:0000:0000:8a2e:0370:7334
# - 压缩格式: 2001:db8:85a3::8a2e:370:7334 (推荐 / recommended)
# - 回环地址: ::1
# - 链路本地: fe80::/10
# - 唯一本地: fd00::/8
# - IPv4映射: ::ffff:192.0.2.1
# - CIDR表示: 2001:db8::/32, fe80::/64, ::1/128

# 参考文档 / Reference documentation:
# - IPv6 支持文档: docs/IPV6_SUPPORT.md
# - 测试文件: tests/test_ipv6_support.py
# - 网络配置测试: tests/test_ipv6_network_config.py
