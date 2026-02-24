# FileProxy 实时流量监控与断点续传功能

## 概述

本次更新为 FileProxy 添加了以下关键功能：

1. **HTTP Range 请求支持（断点续传）** - 支持 Range 头，允许客户端从指定位置继续下载
2. **实时传输监控** - 监控面板显示活跃的文件传输及其进度
3. **HLS 优化配置** - 针对 8 秒 TS 分片、FFmpeg CRF 26 画质优化传输参数

## 功能详情

### 1. HTTP Range 请求支持（断点续传）

#### 特性
- ✅ 支持标准 HTTP Range 请求头
- ✅ 返回 206 Partial Content 状态码
- ✅ 支持 Content-Range 响应头
- ✅ 支持多种 Range 格式：
  - `bytes=0-499` - 指定范围
  - `bytes=500-` - 从指定位置到文件末尾
  - `bytes=-500` - 最后 N 字节（后缀范围）

#### 使用示例

**基本范围请求：**
```bash
curl -H "Range: bytes=0-1023" http://localhost:7889/video/segment.ts
```

**断点续传（从第 1MB 开始）：**
```bash
curl -H "Range: bytes=1048576-" http://localhost:7889/video/segment.ts
```

**获取最后 1MB：**
```bash
curl -H "Range: bytes=-1048576" http://localhost:7889/video/segment.ts
```

#### 响应示例

**完整文件（200 OK）：**
```http
HTTP/1.1 200 OK
Content-Length: 3145728
Accept-Ranges: bytes
Content-Type: video/mp2t
```

**部分内容（206 Partial Content）：**
```http
HTTP/1.1 206 Partial Content
Content-Length: 1024
Content-Range: bytes 0-1023/3145728
Accept-Ranges: bytes
Content-Type: video/mp2t
```

### 2. 实时传输监控

#### 监控端点

**获取活跃传输：**
```bash
curl http://localhost:7889/active-transfers
```

**响应示例：**
```json
{
  "active_transfers": 3,
  "completed_transfers": 0,
  "total_speed_bps": 6291456,
  "total_speed_mbps": 6.0,
  "transfers": [
    {
      "transfer_id": "a1b2c3d4-...",
      "file_path": "segment001.ts",
      "status": "active",
      "bytes_transferred": 1048576,
      "total_size": 3145728,
      "speed_bps": 2097152,
      "progress_percent": 33.33,
      "elapsed": 0.5,
      "client_ip": "192.168.1.100",
      "file_type": "ts"
    }
  ],
  "timestamp": 1698765432.123,
  "worker_pid": 12345
}
```

#### Web 监控面板

访问 `http://localhost:7889/monitor` 查看实时监控面板，包括：

- 📊 **活跃传输数量** - 当前正在进行的传输
- 🚀 **总传输速度** - 所有传输的总速度（MB/s）
- 📡 **传输列表** - 详细的传输信息：
  - 文件名和类型
  - 客户端 IP
  - 传输速度
  - 已传输/总大小
  - 进度百分比（带进度条）
  - 传输状态（活跃/完成/错误/断开）

**监控面板特性：**
- ⏱️ 每 5 秒自动刷新
- 📈 实时进度条显示
- 🎨 状态颜色编码（绿色=活跃，蓝色=完成，红色=错误，黄色=断开）
- 💨 显示实时传输速度

### 3. HLS 优化配置（8秒 TS 分片，CRF 26）

#### 优化参数

针对以下场景优化：
- **分片时长：** 8 秒
- **视频编码：** H.264
- **画质设置：** FFmpeg CRF 26
- **估计文件大小：** 约 3.2 MB/segment

#### 自动优化

系统自动应用以下优化：

```python
{
  "STREAM_CHUNK_SIZE": 131072,      # 128 KB（优化的块大小）
  "BUFFER_SIZE": 524288,             # 512 KB（4倍块大小缓冲）
  "ESTIMATED_SEGMENT_SIZE": 3355443, # 约 3.2 MB
  "RECOMMENDED_BITRATE_MBPS": 3.20   # 推荐比特率
}
```

#### 性能指标

- **传输效率：** 每个 TS 分片约需 26 个 chunk
- **理论传输时间：** 在 2 Mbps 带宽下约 12.8 秒
- **内存使用：** 最大 512 KB 缓冲区
- **适用场景：** 低到中等带宽网络环境

#### 调整其他配置

如需针对不同的 CRF 或分片时长优化，可在代码中调用：

```python
from performance_optimizer import PerformanceOptimizer

# 自定义配置
hls_config = PerformanceOptimizer.get_hls_optimized_config(
    segment_duration=10,  # 10秒分片
    crf_quality=23        # 更高画质
)
```

**支持的 CRF 预设：**
- CRF 18: 高画质（约 1.2 MB/秒）
- CRF 23: 中等画质（约 0.6 MB/秒）
- CRF 26: 推荐画质（约 0.4 MB/秒）
- CRF 28: 低画质（约 0.3 MB/秒）

## 配置说明

### 启用/禁用功能

在 `models/config.py` 中配置：

```python
# 后端模式（必须为 filesystem 才能使用 Range 请求）
BACKEND_MODE = "filesystem"
BACKEND_FILESYSTEM_ROOT = "/data"

# 启用 sendfile（小文件优化，但 Range 请求会自动禁用）
BACKEND_FILESYSTEM_SENDFILE = True

# 流量收集器（用于监控）
TRAFFIC_COLLECTOR_ENABLED = True
```

### 性能调优

**块大小调整：**
```python
# 在 models/config.py 中
STREAM_CHUNK_SIZE = 131072  # 128KB（针对 8秒/CRF26 优化）
BUFFER_SIZE = 524288        # 512KB
```

**监控刷新频率：**
```javascript
// 在 static/js/monitor.js 中
setInterval(refreshData, 5000);  // 5秒刷新一次
```

## 测试

### 运行单元测试

```bash
cd /home/runner/work/YuemPyScripts/YuemPyScripts/Server/FileProxy
python tests/test_range_requests.py
```

**测试内容：**
- ✅ Range 头解析（9个测试用例）
- ✅ HLS 优化配置验证
- ✅ 块大小合理性检查

### 手动测试 Range 请求

**使用 curl 测试：**
```bash
# 测试 Accept-Ranges 头
curl -I http://localhost:7889/test.ts

# 测试部分内容下载
curl -H "Range: bytes=0-1023" http://localhost:7889/test.ts -v

# 测试断点续传
curl -H "Range: bytes=1024-" http://localhost:7889/test.ts -o test_resume.ts
```

**使用 wget 测试断点续传：**
```bash
# 启动下载
wget -c http://localhost:7889/large_file.ts

# 中断后继续（自动使用 Range 头）
wget -c http://localhost:7889/large_file.ts
```

### 测试监控功能

1. 启动服务器
2. 访问 `http://localhost:7889/monitor`
3. 在另一个终端发起下载：
   ```bash
   curl http://localhost:7889/large_file.ts -o /dev/null
   ```
4. 在监控面板观察实时传输进度

## API 参考

### GET /active-transfers

获取当前活跃的文件传输信息。

**响应字段：**
- `active_transfers` (int): 活跃传输数
- `completed_transfers` (int): 已完成传输数
- `total_speed_bps` (float): 总传输速度（字节/秒）
- `total_speed_mbps` (float): 总传输速度（兆比特/秒）
- `transfers` (array): 传输详情列表
  - `transfer_id` (string): 传输唯一标识
  - `file_path` (string): 文件路径
  - `status` (string): 状态（active/completed/error/disconnected）
  - `bytes_transferred` (int): 已传输字节数
  - `total_size` (int|null): 总字节数
  - `speed_bps` (float): 传输速度（字节/秒）
  - `progress_percent` (float|null): 进度百分比
  - `elapsed` (float): 已耗时（秒）
  - `client_ip` (string): 客户端IP
  - `file_type` (string): 文件类型

## 技术实现

### Range 请求处理流程

1. **请求接收** → 检查 `Range` 头
2. **头解析** → 调用 `_parse_range_header()` 解析范围
3. **范围验证** → 验证范围是否有效
4. **文件读取** → 从指定位置开始读取
5. **响应构建** → 返回 206 状态码和 Content-Range 头

### 实时监控实现

1. **传输追踪** → 在 `stream_file_chunks()` 中记录传输信息
2. **进度更新** → 每个 chunk 更新进度和速度
3. **定期清理** → 5秒后自动清理完成/错误的传输记录
4. **API 暴露** → `/active-transfers` 端点提供实时数据

### 性能优化

- **零拷贝传输** → 使用异步文件 I/O（aiofiles）
- **背压控制** → 检测客户端断开，及时停止传输
- **智能缓冲** → 根据文件大小和类型选择合适的块大小
- **连接复用** → HTTP Keep-Alive 和连接池

## 故障排查

### Range 请求不工作

**检查清单：**
1. ✅ 后端模式是否为 `filesystem`
2. ✅ 文件系统根目录是否正确配置
3. ✅ 文件是否存在且可读
4. ✅ Range 头格式是否正确

**查看日志：**
```bash
tail -f logs/proxy_fastapi.log | grep "Range"
```

### 监控面板显示空白

**检查清单：**
1. ✅ `/active-transfers` 端点是否可访问
2. ✅ 浏览器控制台是否有错误
3. ✅ `stream_proxy_service` 是否正确初始化

**测试端点：**
```bash
curl http://localhost:7889/active-transfers
```

### 传输速度慢

**优化建议：**
1. 增加 `STREAM_CHUNK_SIZE`（最大 128KB）
2. 增加 `BUFFER_SIZE`（建议 4倍 chunk size）
3. 启用 `uvloop`：`pip install uvloop`
4. 检查磁盘 I/O 性能

## 未来改进

- [ ] WebSocket 实时推送（替代轮询）
- [ ] 多范围请求支持（multipart/byteranges）
- [ ] 传输暂停/恢复控制
- [ ] 历史传输记录和统计
- [ ] 自适应块大小（根据网络状况动态调整）

## 参考文档

- [RFC 7233 - HTTP Range Requests](https://tools.ietf.org/html/rfc7233)
- [MDN - HTTP Range Requests](https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests)
- [FFmpeg CRF Guide](https://trac.ffmpeg.org/wiki/Encode/H.264#crf)
- [HLS Best Practices](https://developer.apple.com/documentation/http_live_streaming)

## 贡献者

- 实现：GitHub Copilot
- 测试：自动化测试套件
- 文档：本 README

---

**版本：** 2.1.0  
**更新日期：** 2025-10-31  
**许可证：** 与主项目保持一致
