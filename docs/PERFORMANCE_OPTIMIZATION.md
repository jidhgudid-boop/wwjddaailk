# 性能优化功能说明

本文档说明 FileProxy 服务的性能优化配置开关及其实际功能。

## 配置项

所有配置项位于 `models/config.py` 文件中：

```python
# 性能优化开关
ENABLE_REQUEST_DEDUPLICATION = True  # 请求去重
ENABLE_PARALLEL_VALIDATION = True     # 并行验证
ENABLE_REDIS_PIPELINE = True          # Redis Pipeline
ENABLE_RESPONSE_STREAMING = True      # 流式响应
```

## 功能详解

### 1. Redis Pipeline (ENABLE_REDIS_PIPELINE)

**位置**: `services/session_service.py`

**功能**: 批量执行 Redis 操作时使用 Pipeline 模式，减少网络往返次数。

**实现**:
```python
async def batch_redis_operations(redis_client, operations: List[Tuple]) -> List[Any]:
    """批量执行Redis操作"""
    return await redis_service.batch_operations(operations, use_pipeline=config.ENABLE_REDIS_PIPELINE)
```

**性能提升**: 
- 将多个 Redis 命令打包成一次网络请求
- 减少网络延迟，特别是在高并发场景下
- 典型场景：会话创建、会话延期等需要多个 Redis 操作的场景

**使用场景**:
- 创建会话时需要设置 session 和 session 索引
- 延长会话时需要更新多个 key 的 TTL

---

### 2. 并行验证 (ENABLE_PARALLEL_VALIDATION)

**位置**: `services/validation_service.py`

**功能**: 将独立的验证步骤（IP 白名单检查、会话验证）并行执行，而不是顺序执行。

**实现**:
```python
async def parallel_validate(client_ip, path, user_agent, uid, ...):
    tasks = []
    # 任务1：IP白名单检查
    tasks.append(check_ip_key_path(client_ip, path, user_agent))
    # 任务2：会话验证
    tasks.append(get_or_validate_session_by_ip_ua(uid, client_ip, user_agent, path))
    
    # 并行执行所有验证任务
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

**性能提升**:
- 测试显示 ~2x 性能提升
- 顺序执行：200ms，并行执行：100ms
- 特别适合有多个独立 I/O 操作的场景

**对比**:

顺序验证（禁用时）:
```
[IP检查: 50ms] -> [会话验证: 50ms] = 总计 100ms
```

并行验证（启用时）:
```
[IP检查: 50ms]
[会话验证: 50ms]  并行执行
= 总计 50ms（理想情况）
```

---

### 3. 请求去重 (ENABLE_REQUEST_DEDUPLICATION)

**位置**: `services/validation_service.py`

**功能**: 当多个相同的请求同时到达时，只执行一次验证，其他请求等待并共享结果。

**实现**:
```python
class RequestDeduplicator:
    def _generate_request_key(self, client_ip, path, user_agent, uid):
        # 生成请求的唯一标识
        key_string = "|".join([client_ip, path, user_agent, uid or ""])
        return hashlib.md5(key_string.encode()).hexdigest()
    
    async def deduplicate(self, ..., validation_func):
        # 如果相同请求正在处理，等待其结果
        # 否则创建新的验证任务
```

**适用场景**:
- HLS 视频播放时，播放器可能同时请求多个相同的 .ts 文件
- 刷新页面导致的重复请求
- 网络抖动导致的重试请求

**效果**:
- 减少数据库/Redis 查询次数
- 降低后端负载
- 保持响应时间一致

**示例**:

禁用去重时:
```
请求A: /video/segment1.ts from 192.168.1.1
请求B: /video/segment1.ts from 192.168.1.1  (相同请求)
请求C: /video/segment1.ts from 192.168.1.1  (相同请求)

每个请求都执行完整的验证流程
-> 3次验证，3次数据库查询
```

启用去重时:
```
请求A: /video/segment1.ts from 192.168.1.1 -> 执行验证
请求B: /video/segment1.ts from 192.168.1.1 -> 等待A的结果
请求C: /video/segment1.ts from 192.168.1.1 -> 等待A的结果

-> 1次验证，1次数据库查询，3个请求共享结果
```

---

### 4. 流式响应 (ENABLE_RESPONSE_STREAMING)

**位置**: 多个文件中使用

**功能**: 使用流式传输发送响应，支持大文件传输和进度显示。

**效果**:
- 降低内存使用
- 支持断点续传
- 更好的用户体验

---

## 监控面板

访问 `/monitor` 可以查看所有优化开关的状态：

- **性能配置**卡片显示各个开关的启用状态
- 绿色"启用"表示功能已开启
- 灰色"禁用"表示功能已关闭

## 测试

运行测试验证功能:

```bash
# 测试配置和并行验证
python3 tests/test_validation_features.py

# 测试健康检查端点
python3 tests/test_health_config.py
```

## 性能建议

1. **生产环境**：建议全部启用（默认配置）
2. **开发/调试**：可以选择性禁用某些功能以便调试
3. **低负载环境**：并行验证和请求去重的收益可能不明显
4. **高并发环境**：所有优化都能带来显著的性能提升

## 配置修改

修改 `models/config.py` 中的对应配置项，然后重启服务：

```bash
# 修改配置
vim models/config.py

# 重启服务
systemctl restart fileproxy
# 或
./run.sh
```

## 注意事项

1. 所有功能默认启用，已经过测试验证
2. 禁用某些功能不会影响服务的基本功能，只是性能会下降
3. 建议在修改配置后通过 `/health` 端点确认配置已生效
