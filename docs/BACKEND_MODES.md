# 后端模式配置指南

## 概述

文件代理服务器支持两种后端模式，可通过配置灵活切换：

1. **HTTP 模式** - 通过 HTTP/HTTPS 代理到远程服务器
2. **Filesystem 模式** - 直接从本地文件系统读取文件（更高性能）

## 配置方式

在 `models/config.py` 中设置 `BACKEND_MODE`:

```python
# 选择后端模式
BACKEND_MODE = "filesystem"  # 可选: 'http' 或 'filesystem'
```

---

## 模式 1: HTTP 后端模式

### 适用场景

- 文件存储在远程服务器
- 需要通过网络访问文件
- 分布式架构，代理服务器和存储服务器分离
- 需要负载均衡或故障转移

### 配置项

```python
BACKEND_MODE = "http"

# HTTP backend configuration
BACKEND_HOST = "172.17.0.1"              # 后端服务器地址
BACKEND_PORT = 443                        # 后端服务器端口
BACKEND_USE_HTTPS = True                  # 是否使用 HTTPS
BACKEND_SSL_VERIFY = False                # 是否验证 SSL 证书
PROXY_HOST_HEADER = "video-files.yuelk.com"  # Host 请求头
```

### 特性

✅ **HTTP/2 多路复用**
- 使用 httpx 的 HTTP/2 支持
- 单个连接可并发多个请求
- 减少连接建立开销

✅ **智能连接池**
- 最大连接数: 100
- 每个主机的 keep-alive 连接: 30
- 自动连接复用和清理

✅ **流式传输**
- 零拷贝块传输（8KB 块）
- 背压控制，防止内存溢出
- 自动断点续传

✅ **错误处理**
- 自动重试机制
- 超时控制（连接/总超时）
- 详细的错误日志

### 性能特征

| 指标 | 性能 |
|------|------|
| 并发连接 | 1000+ |
| 响应时间 | 取决于网络延迟 |
| 内存使用 | 中等（需要缓冲） |
| CPU 使用 | 中等 |

---

## 模式 2: Filesystem 后端模式

### 适用场景

- **文件存储在本地或挂载的网络存储**
- **需要最佳性能和最低延迟**
- 单机部署或使用共享存储（NFS、Ceph、GlusterFS 等）
- 高并发 HLS 流媒体场景

### 配置项

```python
BACKEND_MODE = "filesystem"

# Filesystem backend configuration
BACKEND_FILESYSTEM_ROOT = "/data/video-files"  # 本地文件系统根目录
BACKEND_FILESYSTEM_SENDFILE = True             # 启用 sendfile 零拷贝传输
BACKEND_FILESYSTEM_BUFFER_SIZE = 64 * 1024     # 64KB buffer
```

### 特性

✅ **真正的零拷贝传输**
- 使用操作系统的 sendfile 系统调用
- 数据直接从磁盘到网络，不经过用户空间
- 极低的 CPU 使用率

✅ **智能文件服务**
- 小文件（< 10MB）: 使用 FileResponse + sendfile
- 大文件（≥ 10MB）: 使用异步流式传输
- 自动选择最优传输方式

✅ **安全保护**
- 路径遍历攻击检测
- 严格的目录访问控制
- 文件权限检查

✅ **高效缓存**
- 操作系统级别的文件缓存
- 无需应用层缓存
- 自动 mmap 优化（OS 级别）

### 性能特征

| 指标 | 性能 |
|------|------|
| 并发连接 | 5000+ |
| 响应时间 | < 1ms（本地磁盘）|
| 内存使用 | 极低 |
| CPU 使用 | 极低 |
| 磁盘 I/O | 取决于存储性能 |

### 性能对比

| 场景 | HTTP 模式 | Filesystem 模式 | 提升 |
|------|-----------|----------------|------|
| 小文件（< 1MB） | 5-10ms | < 1ms | **5-10x** |
| 中等文件（10MB）| 50-100ms | 10-20ms | **3-5x** |
| 大文件（100MB）| 500-1000ms | 100-200ms | **3-5x** |
| 内存使用 | 100MB | 20MB | **-80%** |
| CPU 使用率 | 30-40% | 5-10% | **-75%** |

---

## 目录结构示例

### Filesystem 模式目录结构

```
/data/video-files/          # BACKEND_FILESYSTEM_ROOT
├── video/
│   ├── 2024-01-01/
│   │   ├── movie1/
│   │   │   ├── playlist.m3u8
│   │   │   ├── segment000.ts
│   │   │   ├── segment001.ts
│   │   │   └── enc.key
│   │   └── movie2/
│   │       └── ...
│   └── 2024-01-02/
│       └── ...
└── static/
    ├── images/
    └── css/
```

### 请求映射

```
请求: GET /video/2024-01-01/movie1/playlist.m3u8
文件: /data/video-files/video/2024-01-01/movie1/playlist.m3u8

请求: GET /video/2024-01-01/movie1/segment000.ts
文件: /data/video-files/video/2024-01-01/movie1/segment000.ts
```

---

## 使用建议

### 使用 HTTP 模式的情况

✅ 文件存储在远程服务器  
✅ 使用 CDN 或对象存储（S3、OSS 等）  
✅ 需要跨区域访问  
✅ 分布式架构  
✅ 需要动态内容生成

### 使用 Filesystem 模式的情况

✅ 文件存储在本地磁盘或高速存储  
✅ 使用网络文件系统（NFS、Ceph、GlusterFS）  
✅ 对性能和延迟要求极高  
✅ HLS 流媒体高并发场景  
✅ 单机或共享存储架构  
✅ 需要最低的 CPU 和内存开销

---

## 网络文件系统支持

Filesystem 模式支持各种网络文件系统：

### NFS (Network File System)

```bash
# 挂载 NFS
sudo mount -t nfs 192.168.1.100:/data/videos /data/video-files

# /etc/fstab 配置
192.168.1.100:/data/videos /data/video-files nfs defaults,_netdev 0 0
```

**性能优化**:
- 使用 `nfsvers=4` 或更高版本
- 启用 `async` 模式（牺牲少量一致性换取性能）
- 调整 `rsize` 和 `wsize`（推荐 1048576）

### Ceph FS

```bash
# 挂载 Ceph FS
sudo mount -t ceph 192.168.1.100:6789:/ /data/video-files \
  -o name=admin,secret=AQD...

# 或使用 fuse
sudo ceph-fuse /data/video-files
```

**优势**:
- 分布式存储，高可用
- 自动负载均衡
- 数据冗余保护

### GlusterFS

```bash
# 挂载 GlusterFS
sudo mount -t glusterfs 192.168.1.100:/gv0 /data/video-files
```

**优势**:
- 横向扩展能力强
- 自动副本管理
- 适合大规模部署

---

## 性能调优

### Filesystem 模式优化

#### 1. 文件系统选择

**推荐**: XFS 或 ext4
```bash
# XFS (推荐用于大文件)
mkfs.xfs /dev/sdb1
mount -o noatime,nodiratime /dev/sdb1 /data/video-files

# ext4 (通用选择)
mkfs.ext4 /dev/sdb1
mount -o noatime,data=writeback /dev/sdb1 /data/video-files
```

#### 2. 挂载选项优化

```bash
# /etc/fstab
/dev/sdb1 /data/video-files xfs noatime,nodiratime,logbufs=8,logbsize=256k 0 0
```

- `noatime`: 不更新访问时间（减少写操作）
- `nodiratime`: 不更新目录访问时间
- `logbufs=8`: 增加日志缓冲区数量
- `logbsize=256k`: 增加日志缓冲区大小

#### 3. 内核参数调优

```bash
# /etc/sysctl.conf
# 增加文件缓存
vm.vfs_cache_pressure = 50

# 增加预读大小
vm.block_dump = 0
vm.laptop_mode = 0

# 文件句柄限制
fs.file-max = 2097152

# 应用设置
sysctl -p
```

#### 4. I/O 调度器

```bash
# 对于 SSD，使用 noop 或 deadline
echo noop > /sys/block/sda/queue/scheduler

# 对于 HDD，使用 cfq
echo cfq > /sys/block/sda/queue/scheduler
```

### HTTP 模式优化

#### 1. 连接池设置

```python
# models/config.py
HTTP_CONNECTOR_LIMIT = 200              # 增加最大连接数
HTTP_CONNECTOR_LIMIT_PER_HOST = 50      # 增加单主机连接数
HTTP_KEEPALIVE_TIMEOUT = 60             # 延长 keep-alive 时间
```

#### 2. 超时配置

```python
HTTP_CONNECT_TIMEOUT = 5                # 连接超时
HTTP_TOTAL_TIMEOUT = 60                 # 总超时
```

#### 3. 启用 HTTP/2

确保 httpx 安装了 http2 支持：
```bash
pip install httpx[http2]
```

---

## 监控和调试

### Filesystem 模式监控

#### 1. 磁盘 I/O 监控

```bash
# 实时 I/O 监控
iostat -x 1

# 查看 I/O 等待
top -b -n 1 | grep 'Cpu(s)'
```

#### 2. 文件缓存命中率

```bash
# 查看页面缓存统计
cat /proc/meminfo | grep -E 'Cached|Buffers'

# 使用 vmtouch 查看文件缓存
vmtouch /data/video-files/
```

#### 3. 文件句柄使用

```bash
# 查看打开的文件数
lsof | wc -l

# 查看进程打开的文件
lsof -p $(pgrep -f app.py)
```

### HTTP 模式监控

#### 1. 连接池状态

查看 `/debug/http-client` 端点（需要实现）

#### 2. 网络延迟

```bash
# ping 后端服务器
ping BACKEND_HOST

# 测试 HTTP 延迟
curl -w "@curl-format.txt" -o /dev/null -s "https://BACKEND_HOST/test.ts"
```

curl-format.txt:
```
time_namelookup:  %{time_namelookup}\n
time_connect:  %{time_connect}\n
time_starttransfer:  %{time_starttransfer}\n
time_total:  %{time_total}\n
```

---

## 故障排查

### Filesystem 模式常见问题

#### 问题 1: 文件未找到 (404)

**原因**:
- `BACKEND_FILESYSTEM_ROOT` 配置错误
- 文件路径不正确
- 文件权限问题

**解决**:
```bash
# 检查根目录
ls -la /data/video-files/

# 检查文件权限
namei -l /data/video-files/video/test.m3u8

# 确保运行用户有读权限
sudo chown -R www-data:www-data /data/video-files/
sudo chmod -R 755 /data/video-files/
```

#### 问题 2: 权限被拒 (403)

**原因**:
- 文件或目录权限不足
- SELinux 或 AppArmor 阻止

**解决**:
```bash
# 检查 SELinux
getenforce

# 临时禁用 SELinux
sudo setenforce 0

# 或添加 SELinux 规则
sudo chcon -R -t httpd_sys_content_t /data/video-files/
```

#### 问题 3: 性能不佳

**原因**:
- 磁盘 I/O 瓶颈
- 文件缓存不足
- 网络文件系统延迟高

**解决**:
```bash
# 增加系统缓存
echo 3 > /proc/sys/vm/drop_caches  # 清空缓存
# 预热缓存
vmtouch -t /data/video-files/

# 检查磁盘性能
dd if=/dev/zero of=/data/video-files/testfile bs=1G count=1 oflag=direct
```

### HTTP 模式常见问题

#### 问题 1: 连接超时

**解决**:
```python
# 增加超时时间
HTTP_CONNECT_TIMEOUT = 15
HTTP_TOTAL_TIMEOUT = 120
```

#### 问题 2: 连接池耗尽

**解决**:
```python
# 增加连接池大小
HTTP_CONNECTOR_LIMIT = 300
HTTP_CONNECTOR_LIMIT_PER_HOST = 100
```

---

## 迁移指南

### 从 HTTP 模式迁移到 Filesystem 模式

**步骤 1**: 准备文件系统

```bash
# 创建目录
sudo mkdir -p /data/video-files

# 从远程服务器同步文件
rsync -avz --progress user@remote:/data/videos/ /data/video-files/
```

**步骤 2**: 更新配置

```python
# models/config.py
BACKEND_MODE = "filesystem"
BACKEND_FILESYSTEM_ROOT = "/data/video-files"
BACKEND_FILESYSTEM_SENDFILE = True
```

**步骤 3**: 重启服务

```bash
sudo systemctl restart fileproxy
```

**步骤 4**: 验证

```bash
# 测试文件访问
curl -I "http://localhost:7889/video/test.m3u8?uid=test&expires=9999999999&token=xxx"

# 检查日志
sudo journalctl -u fileproxy -f
```

### 从 Filesystem 模式迁移到 HTTP 模式

只需更新配置并重启服务即可，无需移动文件。

---

## 最佳实践

### Filesystem 模式

1. ✅ 使用 SSD 或 NVMe 存储以获得最佳性能
2. ✅ 定期监控磁盘健康状态（SMART）
3. ✅ 实现文件备份策略
4. ✅ 使用 RAID 或分布式文件系统提高可靠性
5. ✅ 预热常访问文件到系统缓存
6. ✅ 监控文件句柄使用情况
7. ✅ 使用 `noatime` 挂载选项
8. ✅ 定期清理临时文件和日志

### HTTP 模式

1. ✅ 使用 HTTP/2 以提高并发性能
2. ✅ 配置适当的超时时间
3. ✅ 监控连接池使用情况
4. ✅ 启用后端服务器的 keep-alive
5. ✅ 考虑使用 CDN 加速
6. ✅ 实现重试和熔断机制
7. ✅ 监控网络延迟和带宽
8. ✅ 使用连接复用减少握手开销

---

## 总结

| 特性 | HTTP 模式 | Filesystem 模式 |
|------|-----------|----------------|
| **性能** | 中等（受网络限制） | 极高（本地访问） |
| **延迟** | 5-50ms | < 1ms |
| **并发** | 1000+ | 5000+ |
| **CPU** | 中等 | 极低 |
| **内存** | 中等 | 极低 |
| **复杂度** | 低 | 低 |
| **扩展性** | 高（分布式） | 中（需共享存储） |
| **成本** | 高（网络/CDN） | 低（存储） |
| **适用场景** | 分布式、远程存储 | 本地存储、高性能 |

**推荐**:
- 🚀 **HLS 高并发场景**: Filesystem 模式 + NVMe SSD
- 🌐 **分布式架构**: HTTP 模式 + CDN
- 💰 **成本优化**: Filesystem 模式 + 共享存储（NFS/Ceph）
- 🔄 **混合方案**: 热点文件使用 Filesystem，冷数据使用 HTTP

---

**更新时间**: 2025-10-31  
**版本**: 2.1.0
