# 文件传输策略配置指南

## 概述

FileProxy 使用简化的二层文件传输策略，根据文件大小自动选择最优的传输方式。您只需在 `models/config.py` 中配置一个阈值参数。

## 快速配置

**只需配置一个参数：**

```python
# models/config.py

# 流式传输阈值：>= 此值使用 StreamingResponse，< 此值使用 FileResponse
STREAMING_THRESHOLD = 1 * 1024 * 1024  # 1MB（默认）
```

**常见配置示例：**

| 场景 | STREAMING_THRESHOLD | 说明 |
|------|---------------------|------|
| 标准配置（默认） | 1MB | 适合大多数场景 |
| 硬盘 IO 慢的 VPS | 100KB - 500KB | 更多文件使用流式，减少 IO 压力 |
| 高性能服务器 | 5MB - 10MB | 更多文件使用 sendfile，性能更好 |
| HLS 视频流 | 1MB - 2MB | ts 文件通常 2-5MB，使用流式 |

## 配置参数

### STREAMING_THRESHOLD（唯一阈值）

```python
STREAMING_THRESHOLD = 1 * 1024 * 1024  # 1MB
```

**作用：** 
- **文件 < 阈值**: 使用 `FileResponse` + sendfile（零拷贝传输）
- **文件 >= 阈值**: 使用 `StreamingResponse`（流式传输，显示进度）

**特点对比：**

| 传输方式 | 何时使用 | 优点 | 缺点 |
|---------|---------|------|------|
| FileResponse | < STREAMING_THRESHOLD | • 零拷贝，性能最优<br>• CPU 占用极低<br>• 内存占用极低 | • 不支持 Range 请求 |
| StreamingResponse | >= STREAMING_THRESHOLD | • 支持 Range 请求<br>• 显示下载进度<br>• 内存占用低<br>• 适合大文件 | • 略多的系统调用 |

## 配置示例

### 场景 1：标准配置（默认推荐）

```python
# models/config.py

STREAMING_THRESHOLD = 1 * 1024 * 1024  # 1MB
```

**适用于：**
- 大部分场景
- 硬盘性能正常的服务器
- 文件大小混合的场景

### 场景 2：硬盘 IO 性能差的 VPS

```python
# models/config.py

STREAMING_THRESHOLD = 100 * 1024  # 100KB
# 或者
STREAMING_THRESHOLD = 500 * 1024  # 500KB
```

**为什么降低阈值？**
- 硬盘慢时，一次性读取大文件会造成延迟
- 流式传输边读边传，首字节时间更短
- 用户立即看到下载开始，体验更好

**适用于：**
- 廉价 VPS（硬盘读取 < 50MB/s）
- iostat 显示 wa% > 20%
- 用户反映下载等待时间长

### 场景 3：高性能服务器

```python
# models/config.py

STREAMING_THRESHOLD = 5 * 1024 * 1024  # 5MB
# 或者
STREAMING_THRESHOLD = 10 * 1024 * 1024  # 10MB
```

**为什么提高阈值？**
- 更多文件使用 FileResponse (sendfile)
- sendfile 是零拷贝，性能最优
- 高性能硬盘一次性读取很快

**适用于：**
- SSD 服务器
- 高性能硬盘（读取 > 200MB/s）
- 内存充足（> 16GB）

### 场景 4：HLS 视频流

```python
# models/config.py

STREAMING_THRESHOLD = 1 * 1024 * 1024  # 1MB
# 或者
STREAMING_THRESHOLD = 2 * 1024 * 1024  # 2MB
```

**说明：**
- HLS 切片（.ts 文件）通常 2-5MB
- 使用流式传输确保进度显示
- m3u8 文件很小，自动使用 FileResponse

## 传输策略选择流程

```
文件请求
   |
   v
文件大小 >= STREAMING_THRESHOLD?
   |
   |-- 否 --> FileResponse (sendfile 零拷贝，性能最优)
   |
   |-- 是 --> StreamingResponse (流式传输，显示进度)
```

**简单明了：只有一个判断！**

## 如何测试硬盘性能

### 测试读取速度

```bash
# 测试顺序读取
dd if=/data/large_file.mp4 of=/dev/null bs=1M count=100

# 查看结果
# 100+0 records in
# 100+0 records out
# 104857600 bytes (105 MB, 100 MiB) copied, 2.5 s, 41.9 MB/s
```

**判断标准：**
- 速度 > 100MB/s：硬盘性能好，可以使用 5-10MB 阈值
- 速度 50-100MB/s：硬盘性能一般，使用 1-2MB 阈值（默认）
- 速度 < 50MB/s：硬盘性能差，使用 100-500KB 阈值

### 查看 IO 等待

```bash
# 实时查看 IO 等待时间
iostat -x 1

# 关注 %util 和 await 列
# wa% > 20%：IO 压力大，降低阈值
```

## 监控和调优

### 查看当前配置

```bash
cd Server/FileProxy
python -c "from models.config import config; print(f'STREAMING_THRESHOLD: {config.STREAMING_THRESHOLD/(1024*1024):.1f}MB')"
```

### 查看传输方式分布

```bash
# 查看日志中的响应类型
tail -f logs/proxy_fastapi.log | grep "使用.*Response"

# 应该看到：
# 使用 FileResponse (sendfile): small.txt, size=512000
# 使用 StreamingResponse (流式): video.mp4, size=5242880
```

### 调优建议

**如果感觉下载等待时间长：**
- 降低 `STREAMING_THRESHOLD`（例如从 1MB 降到 500KB）
- 更多文件使用流式传输，首字节时间更短

**如果 CPU 占用高：**
- 提高 `STREAMING_THRESHOLD`（例如从 1MB 升到 5MB）
- 更多文件使用 FileResponse (sendfile)，CPU 占用更低

**如果内存占用高：**
- 配置已经很优化了（两种方式内存占用都很低）
- 检查并发连接数和 worker 数量

## 常见问题

### Q: 只有一个阈值够用吗？

A: 够用！这个简化的配置已经能满足 99% 的场景：
- 小文件用 FileResponse（性能最优）
- 大文件用 StreamingResponse（显示进度）
- 简单清晰，易于理解和调整

### Q: StreamingResponse 会影响下载速度吗？

A: 不会。StreamingResponse 只是改变传输方式，不影响实际速度。

### Q: 我应该设置多大的阈值？

A: **从 1MB 开始**，然后根据实际情况调整：
- 硬盘慢 → 降到 100-500KB
- 硬盘快 → 升到 5-10MB
- 不确定 → 保持 1MB（默认）

### Q: Range 请求怎么处理？

A: Range 请求（断点续传）**自动使用** StreamingResponse，不受阈值限制。

### Q: 修改配置后需要重启吗？

A: 是的，需要重启服务器：
```bash
# 重启服务
./run.sh

# 或者使用 systemd
sudo systemctl restart fileproxy
```

### Q: 如何验证配置生效？

A: 查看日志：
```bash
tail -f logs/proxy_fastapi.log | grep "使用.*Response"

# 小文件应该显示：使用 FileResponse
# 大文件应该显示：使用 StreamingResponse
```

## 配置示例总结

```python
# models/config.py

# === 场景选择 ===

# 场景 1: 标准配置（推荐）
STREAMING_THRESHOLD = 1 * 1024 * 1024  # 1MB

# 场景 2: 硬盘 IO 慢的 VPS
# STREAMING_THRESHOLD = 100 * 1024  # 100KB

# 场景 3: 高性能服务器
# STREAMING_THRESHOLD = 5 * 1024 * 1024  # 5MB

# 场景 4: 极度节省内存
# STREAMING_THRESHOLD = 0  # 全部使用流式传输
```

## 总结

通过在 `models/config.py` 中调整**一个参数** `STREAMING_THRESHOLD`，即可轻松配置文件传输策略：

```python
STREAMING_THRESHOLD = 1 * 1024 * 1024  # 1MB（可调整）
```

**简单、清晰、易用！**

### 1. FILE_RESPONSE_THRESHOLD（小文件阈值）

```python
FILE_RESPONSE_THRESHOLD = 10 * 1024 * 1024  # 10MB
```

**作用：** 小于此大小的文件使用 `FileResponse` + sendfile（零拷贝传输）

**特点：**
- ✓ 性能最优（零拷贝，内核直接传输）
- ✓ CPU 使用率最低
- ✓ 内存占用最小
- ✓ 自动包含 Content-Length

**适用场景：**
- HLS 视频切片（.ts 文件，通常 2-5MB）
- 小图片、CSS、JS 文件
- 小视频片段

**调整建议：**
- 内存充足：可设为 20MB 或 50MB
- 内存有限：保持 10MB 或降至 5MB

### 2. RESPONSE_SIZE_THRESHOLD_SMALL（中等文件阈值）

```python
RESPONSE_SIZE_THRESHOLD_SMALL = 32 * 1024 * 1024  # 32MB
```

**作用：** 介于 FILE_RESPONSE_THRESHOLD 和此值之间的文件使用 `Response`（直接读入内存）

**特点：**
- ✓ 确保 Content-Length 正确显示（浏览器可显示下载进度）
- ✓ 性能良好
- ⚠️ 内存占用：文件大小 × 并发数

**适用场景：**
- 中等大小的视频文件
- 需要显示下载进度的文件
- 并发下载数不高的场景

**调整建议：**
- 内存充足（>16GB）：可设为 64MB 或 128MB
- 内存有限（<8GB）：降至 16MB 或 20MB
- 高并发场景：降至 16MB

### 3. StreamingResponse（大文件）

**作用：** 大于 RESPONSE_SIZE_THRESHOLD_SMALL 的文件使用 `StreamingResponse`（流式传输）

**特点：**
- ✓ 内存占用低（仅占用 chunk 大小）
- ✓ 支持超大文件（GB 级别）
- ✓ 支持高并发
- ✓ 包含 Content-Length（已优化）

**适用场景：**
- 大视频文件（>32MB）
- 电影、电视剧
- 高并发下载

## 配置示例

### 场景 1：小内存服务器（< 4GB）

```python
# models/config.py

FILE_RESPONSE_THRESHOLD = 5 * 1024 * 1024      # 5MB
RESPONSE_SIZE_THRESHOLD_SMALL = 16 * 1024 * 1024  # 16MB
```

**说明：** 降低阈值以减少内存占用

### 场景 2：标准服务器（4-8GB）

```python
# models/config.py

FILE_RESPONSE_THRESHOLD = 10 * 1024 * 1024     # 10MB（默认）
RESPONSE_SIZE_THRESHOLD_SMALL = 32 * 1024 * 1024  # 32MB（默认）
```

**说明：** 平衡性能和内存，适合大多数场景

### 场景 3：高配服务器（> 16GB）

```python
# models/config.py

FILE_RESPONSE_THRESHOLD = 20 * 1024 * 1024     # 20MB
RESPONSE_SIZE_THRESHOLD_SMALL = 64 * 1024 * 1024  # 64MB
```

**说明：** 充分利用内存，提升性能

### 场景 4：HLS 视频流优化

```python
# models/config.py

FILE_RESPONSE_THRESHOLD = 10 * 1024 * 1024     # 10MB
RESPONSE_SIZE_THRESHOLD_SMALL = 32 * 1024 * 1024  # 32MB
```

**说明：** HLS 切片通常 2-5MB，使用默认配置最优

### 场景 5：硬盘 IO 性能差的 VPS

```python
# models/config.py

# 硬盘 IO 差时，应该降低阈值，更多使用流式传输
# 流式传输使用小块读取，减少对硬盘的单次大量读取压力
FILE_RESPONSE_THRESHOLD = 2 * 1024 * 1024      # 2MB（从 10MB 降低）
RESPONSE_SIZE_THRESHOLD_SMALL = 8 * 1024 * 1024   # 8MB（从 32MB 降低）

# 同时可以调整块大小，使用更小的块减少 IO 压力
STREAM_CHUNK_SIZE = 32 * 1024  # 32KB（从默认的 64KB 或更大降低）
```

**说明：** 
- **为什么降低阈值？** 
  - FileResponse (sendfile) 需要一次性读取整个文件到内核缓冲区
  - Response 需要一次性读取整个文件到内存
  - 硬盘 IO 差时，大文件的一次性读取会造成严重延迟
  
- **流式传输的优势：**
  - 分块读取（默认 64KB 或可配置的更小块）
  - 边读边传，不需要等待整个文件读取完成
  - 减少单次 IO 压力
  - 用户可以更快看到响应（首字节时间更短）

- **权衡：**
  - 吞吐量可能略降（更多系统调用）
  - 但用户体验更好（响应更快，不会卡顿）
  - 适合 IO 受限场景

**实际效果：**
```
硬盘 IO 差的情况下：
- 10MB 文件用 FileResponse：可能需要 2-3 秒才开始传输（等待读取）
- 10MB 文件用 StreamingResponse：立即开始传输（边读边传）

用户感知：
- FileResponse：等待很久才开始下载
- StreamingResponse：立即开始下载，虽然速度可能相同但体验更好
```

### 场景 6：高并发场景

```python
# models/config.py

FILE_RESPONSE_THRESHOLD = 5 * 1024 * 1024      # 5MB
RESPONSE_SIZE_THRESHOLD_SMALL = 16 * 1024 * 1024  # 16MB
```

**说明：** 降低阈值以支持更多并发连接

## 传输策略选择流程

```
文件请求
   |
   v
文件大小 < FILE_RESPONSE_THRESHOLD (10MB)?
   |
   |-- 是 --> FileResponse (sendfile零拷贝)
   |
   |-- 否 --> 文件大小 < RESPONSE_SIZE_THRESHOLD_SMALL (32MB)?
              |
              |-- 是 --> Response (直接读入内存)
              |
              |-- 否 --> StreamingResponse (流式传输)
```

## 性能对比

| 传输方式 | 内存占用 | CPU 占用 | 吞吐量 | Content-Length | 推荐场景 |
|---------|---------|---------|--------|----------------|---------|
| FileResponse | 极低 | 极低 | 最高 | ✓ | 小文件 |
| Response | 文件大小 | 低 | 高 | ✓ | 中等文件 |
| StreamingResponse | 极低 | 中 | 高 | ✓ | 大文件 |

## 监控和调优

### 1. 查看当前配置

```bash
cd Server/FileProxy
grep -E "(FILE_RESPONSE_THRESHOLD|RESPONSE_SIZE_THRESHOLD)" models/config.py
```

### 2. 监控内存使用

```bash
# 查看进程内存占用
ps aux | grep gunicorn

# 实时监控
top -p $(pgrep -f gunicorn | tr '\n' ',' | sed 's/,$//')
```

### 3. 查看传输方式分布

```bash
# 查看日志中的响应类型
tail -f logs/proxy_fastapi.log | grep "使用.*Response"
```

### 4. 诊断硬盘 IO 性能

**测试硬盘读取速度：**
```bash
# 测试顺序读取速度
dd if=/data/test_large_file.mp4 of=/dev/null bs=1M count=100 iflag=direct

# 测试随机读取（更能反映实际场景）
fio --name=randread --ioengine=libaio --iodepth=16 --rw=randread \
    --bs=64k --direct=1 --size=1G --numjobs=1 --runtime=60 \
    --group_reporting --filename=/data/test_file
```

**判断 IO 性能：**
- 顺序读取 > 100MB/s：IO 性能良好，使用默认配置
- 顺序读取 50-100MB/s：IO 性能一般，考虑降低阈值
- 顺序读取 < 50MB/s：IO 性能差，**强烈建议使用场景 5 配置**

**观察系统 IO 等待：**
```bash
# 查看 IO 等待时间（wa%）
iostat -x 1

# wa% > 20%：IO 压力大，建议降低阈值
# wa% > 50%：IO 严重瓶颈，必须降低阈值到 2MB/8MB
```

### 5. 调优建议

**如果内存使用过高：**
- 降低 `RESPONSE_SIZE_THRESHOLD_SMALL`
- 降低 `FILE_RESPONSE_THRESHOLD`
- 减少 worker 数量

**如果性能不够：**
- 增加 `FILE_RESPONSE_THRESHOLD`（更多文件用 sendfile）
- 增加 worker 数量
- 启用 uvloop

**如果 OOM（内存不足）：**
- 立即降低 `RESPONSE_SIZE_THRESHOLD_SMALL` 至 16MB 或更低
- 检查并发连接数
- 考虑增加服务器内存

## 常见问题

### Q: 为什么不全部使用 StreamingResponse？

A: 小文件使用 FileResponse (sendfile) 性能最优，CPU 和内存占用都最低。

### Q: Content-Length 会丢失吗？

A: 不会。我们已经优化了所有三种传输方式，都正确设置 Content-Length。

### Q: 修改配置后需要重启吗？

A: 是的，需要重启服务器：
```bash
# 如果使用 systemd
sudo systemctl restart fileproxy

# 或者
./run.sh
```

### Q: 如何知道我应该用哪个配置？

A: 从默认配置开始，监控一段时间后根据实际情况调整：
- 内存充足 → 增加阈值
- 内存紧张 → 降低阈值
- 文件普遍较小 → 降低阈值
- 文件普遍较大 → 使用默认或增加 FILE_RESPONSE_THRESHOLD
- **硬盘 IO 差（VPS/HDD）→ 大幅降低阈值，使用流式传输**

### Q: 我的 VPS 硬盘很慢，应该怎么配置？

A: **强烈推荐使用场景 5 配置（硬盘 IO 差的 VPS）：**

```python
FILE_RESPONSE_THRESHOLD = 2 * 1024 * 1024      # 2MB
RESPONSE_SIZE_THRESHOLD_SMALL = 8 * 1024 * 1024   # 8MB
```

**原因：**
- 硬盘 IO 慢时，一次性读取大文件会造成严重延迟
- 流式传输边读边传，首字节时间更短
- 用户体验更好（不会等很久才开始下载）

**如何判断硬盘 IO 是否慢？**
```bash
# 测试读取速度
dd if=/data/large_file.mp4 of=/dev/null bs=1M count=100

# 如果速度 < 50MB/s，就属于 IO 慢
# 如果 iostat 显示 wa% > 20%，就需要优化配置
```

### Q: StreamingResponse 会影响下载速度吗？

A: 不会。StreamingResponse 只是改变了传输方式（分块传输），不影响实际下载速度。

**对比：**
- FileResponse：等待整个文件读取 → 开始传输
- StreamingResponse：立即开始读取第一块 → 边读边传

在硬盘 IO 慢的情况下，StreamingResponse 反而让用户感觉更快（立即开始下载）。

### Q: 为什么硬盘慢时要用更小的文件也流式传输？

A: 关键在于**首字节时间（TTFB）**：

**场景：VPS 硬盘很慢，5MB 文件**

使用 FileResponse：
```
读取 5MB 文件（耗时 2 秒）→ 等待 → 开始传输
用户等待：2 秒后才看到下载开始
```

使用 StreamingResponse：
```
读取 64KB（耗时 0.02 秒）→ 立即传输 → 读取下一块 → 传输 → ...
用户等待：0.02 秒就开始下载
```

**结论：** 虽然总时间可能相近，但 StreamingResponse 让用户立即看到反馈，体验更好。

## 总结

通过在 `models/config.py` 中调整以下参数，即可轻松配置文件传输策略：

```python
# 小文件阈值（使用 sendfile）
FILE_RESPONSE_THRESHOLD = 10 * 1024 * 1024  # 可调整

# 流式传输阈值（超过此值使用 StreamingResponse）
RESPONSE_SIZE_THRESHOLD_SMALL = 32 * 1024 * 1024  # 可调整
```

根据服务器配置和业务需求调整这两个值，即可获得最佳性能。
