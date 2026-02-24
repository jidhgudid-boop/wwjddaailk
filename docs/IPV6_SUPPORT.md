# FileProxy IPv6 支持文档

## 概述

FileProxy 完全支持 IPv6，包括：
- ✅ IPv6 地址验证
- ✅ IPv6 CIDR 范围匹配
- ✅ IPv6 固定白名单
- ✅ IPv4/IPv6 双栈支持
- ✅ IPv6 客户端 IP 提取
- ✅ 混合 IPv4/IPv6 场景

## IPv6 支持验证

### 运行测试

```bash
# 测试 IPv6 地址处理和 CIDR 匹配
cd tools/FileProxy
python tests/test_ipv6_support.py

# 测试 IPv6 网络配置
python tests/test_ipv6_network_config.py
```

### 测试结果

所有 IPv6 测试均通过，包括：
1. IPv6 地址验证
2. IPv6 CIDR 表示法
3. IPv6 CIDR 范围匹配
4. IPv6 固定白名单
5. IPv6 地址规范化
6. IPv4/IPv6 混合场景
7. IPv6 边缘情况
8. IPv6 CIDR 扩展示例

## 配置说明

### 服务器绑定

FileProxy 已配置为使用双栈绑定 (IPv4 + IPv6)：

#### app.py
```python
uvicorn.run(
    "app:app",
    host="::",  # 双栈绑定 - 同时支持IPv4和IPv6
    port=7889,
    ...
)
```

#### gunicorn_fastapi.conf.py
```python
bind = "[::]:7889"  # 双栈绑定 - 同时支持IPv4和IPv6
```

#### run.sh
```bash
# 生产环境
gunicorn -c gunicorn_fastapi.conf.py --bind "[::]:7889" app:app

# 开发环境
uvicorn app:app --host :: --port 7889
```

### 双栈工作原理

使用 `::` 绑定时：
- 服务器监听所有 IPv6 地址
- 默认情况下（IPV6_V6ONLY=0），也接受 IPv4 连接
- IPv4 客户端通过 IPv4 映射地址（::ffff:x.x.x.x）连接

## 使用示例

### 1. 固定白名单配置

在 `models/config.py` 中配置混合 IPv4/IPv6 白名单：

```python
FIXED_IP_WHITELIST = [
    # IPv4 地址
    "192.168.1.100",
    "10.0.0.0/24",
    
    # IPv6 地址
    "2001:db8::1",
    "fe80::/64",
    "::1",
    
    # IPv4 映射的 IPv6 地址
    "::ffff:192.0.2.1",
]
```

### 2. IPv6 地址格式

支持的 IPv6 地址格式：

```python
# 完整格式
"2001:0db8:85a3:0000:0000:8a2e:0370:7334"

# 压缩格式（推荐）
"2001:db8:85a3::8a2e:370:7334"

# 回环地址
"::1"

# 链路本地地址
"fe80::1"

# IPv4 映射
"::ffff:192.0.2.1"
```

### 3. IPv6 CIDR 范围

支持的 CIDR 表示法：

```python
# /32 网络（推荐用于组织）
"2001:db8::/32"

# /64 网络（推荐用于子网）
"2001:db8:1::/64"

# /128 单个地址
"2001:db8::1/128"

# 链路本地范围
"fe80::/10"
```

### 4. 客户端 IP 提取

IPv6 客户端 IP 自动从以下来源提取：

```python
# 优先级顺序：
1. X-Forwarded-For 头（支持 IPv6）
2. X-Real-IP 头（支持 IPv6）
3. request.client.host（原始连接 IP）
```

示例：
```
X-Forwarded-For: 2001:db8::1
X-Real-IP: fe80::1
直接连接: ::ffff:192.0.2.1 (IPv4 映射)
```

## API 端点示例

### 监控面板

访问监控面板（支持 IPv4 和 IPv6）：

```bash
# IPv4
http://192.168.1.100:7889/monitor

# IPv6
http://[2001:db8::1]:7889/monitor

# 本地回环 (IPv6)
http://[::1]:7889/monitor
```

### 代理请求

```bash
# IPv6 客户端请求示例
curl -H "X-Real-IP: 2001:db8::1" \
     http://[::1]:7889/proxy/video/test.m3u8
```

## 测试场景

### 1. IPv6 基础功能测试

```python
from utils.cidr_matcher import CIDRMatcher

# 验证 IPv6 地址
is_valid = CIDRMatcher.is_valid_ip("2001:db8::1")
# 返回: True

# IPv6 CIDR 匹配
is_in_range = CIDRMatcher.ip_in_cidr(
    "2001:db8::1", 
    "2001:db8::/32"
)
# 返回: True
```

### 2. 固定白名单测试

```python
from utils.cidr_matcher import CIDRMatcher

whitelist = [
    "192.168.1.0/24",  # IPv4
    "2001:db8::/32",   # IPv6
    "::1",             # IPv6 回环
]

# IPv6 地址匹配
is_match, pattern = CIDRMatcher.match_ip_against_patterns(
    "2001:db8::1",
    whitelist
)
# 返回: (True, "2001:db8::/32")

# IPv4 地址匹配（同一白名单）
is_match, pattern = CIDRMatcher.match_ip_against_patterns(
    "192.168.1.100",
    whitelist
)
# 返回: (True, "192.168.1.0/24")
```

### 3. 混合环境测试

```python
# 模拟 IPv4 和 IPv6 客户端同时访问
test_clients = [
    "192.168.1.100",     # IPv4
    "2001:db8::1",       # IPv6
    "::ffff:10.0.0.1",   # IPv4 映射到 IPv6
    "fe80::1",           # IPv6 链路本地
]

for client_ip in test_clients:
    is_match, pattern = CIDRMatcher.match_ip_against_patterns(
        client_ip,
        whitelist
    )
    print(f"{client_ip}: {is_match} ({pattern})")
```

## 部署注意事项

### 1. 防火墙配置

确保防火墙允许 IPv6 连接：

```bash
# UFW (Ubuntu)
sudo ufw allow 7889/tcp

# firewalld (CentOS/RHEL)
sudo firewall-cmd --add-port=7889/tcp --permanent
sudo firewall-cmd --reload
```

### 2. 反向代理配置

#### Nginx

```nginx
upstream fileproxy {
    # IPv4
    server 127.0.0.1:7889;
    
    # IPv6
    server [::1]:7889;
}

server {
    listen 80;
    listen [::]:80;  # IPv6 监听
    
    server_name example.com;
    
    location / {
        proxy_pass http://fileproxy;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### Apache

```apache
<VirtualHost *:80 [::]:80>
    ServerName example.com
    
    ProxyPreserveHost On
    ProxyPass / http://[::1]:7889/
    ProxyPassReverse / http://[::1]:7889/
    
    RequestHeader set X-Forwarded-For %{REMOTE_ADDR}s
</VirtualHost>
```

### 3. Docker 配置

```yaml
# docker-compose.yml
version: '3'
services:
  fileproxy:
    image: fileproxy:latest
    ports:
      - "7889:7889"      # IPv4
      - "[::]:7889:7889" # IPv6
    environment:
      - IPV6_ENABLED=true
    sysctls:
      - net.ipv6.conf.all.disable_ipv6=0
```

## 故障排查

### 问题 1: IPv6 连接失败

**症状**: 无法通过 IPv6 地址连接

**解决方案**:
```bash
# 1. 检查系统 IPv6 支持
python -c "import socket; print('IPv6:', socket.has_ipv6)"

# 2. 检查 IPv6 地址
ip -6 addr show

# 3. 测试 IPv6 连接
curl -6 http://[::1]:7889/health
```

### 问题 2: IPv4 映射问题

**症状**: IPv4 客户端无法连接到双栈服务器

**解决方案**:
```python
# 确保 IPV6_V6ONLY 设置为 0
# 在 gunicorn worker 中自动处理
```

### 问题 3: 白名单不匹配 IPv6

**症状**: IPv6 地址未被白名单识别

**解决方案**:
```bash
# 运行 IPv6 测试
python tests/test_ipv6_support.py

# 检查白名单配置
grep FIXED_IP_WHITELIST models/config.py
```

## 性能优化

### IPv6 性能建议

1. **使用 CIDR 范围**: 相比单个 IP，CIDR 范围更高效
   ```python
   # 好
   "2001:db8::/32"
   
   # 不推荐（除非必要）
   ["2001:db8::1", "2001:db8::2", ...]
   ```

2. **DNS 配置**: 优先使用 AAAA 记录
   ```
   example.com.  IN  AAAA  2001:db8::1
   example.com.  IN  A     192.0.2.1
   ```

3. **连接池**: HTTP/2 在 IPv6 上表现更好
   - 减少连接建立开销
   - 多路复用提高效率

## 兼容性

### Python 版本
- ✅ Python 3.8+
- ✅ ipaddress 模块（标准库）

### 操作系统
- ✅ Linux (kernel 2.6+)
- ✅ Ubuntu/Debian
- ✅ CentOS/RHEL
- ✅ macOS
- ⚠️ Windows（需要额外配置）

### 容器环境
- ✅ Docker（需要 IPv6 支持）
- ✅ Kubernetes（需要 IPv6 Service）
- ⚠️ 某些云平台可能限制 IPv6

## 更新日志

### 2024-12-08
- ✅ 完成 IPv6 全面支持验证
- ✅ 创建综合 IPv6 测试套件
- ✅ 更新配置文件支持双栈绑定
- ✅ 添加 IPv6 文档和示例
- ✅ 验证所有 IP 处理组件支持 IPv6

## 参考资源

- [RFC 4291 - IPv6 地址架构](https://tools.ietf.org/html/rfc4291)
- [RFC 4193 - 唯一本地 IPv6 单播地址](https://tools.ietf.org/html/rfc4193)
- [Python ipaddress 模块文档](https://docs.python.org/3/library/ipaddress.html)
- [Uvicorn IPv6 配置](https://www.uvicorn.org/deployment/)

## 总结

FileProxy 提供完整的 IPv6 支持：

1. **IP 处理层**: CIDRMatcher 完全支持 IPv6 地址和 CIDR
2. **验证层**: 白名单和会话验证支持 IPv6
3. **网络层**: 服务器配置支持 IPv4/IPv6 双栈
4. **客户端层**: 正确提取和处理 IPv6 客户端地址

通过本文档中的测试和配置，可以确保 FileProxy 在 IPv6 环境中正常运行。
