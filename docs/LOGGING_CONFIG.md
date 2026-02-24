# 日志和调试配置说明

## 日志配置

应用有两种类型的日志：

### 1. 应用日志（Application Logs）

在 `models/config.py` 中可以配置应用日志相关参数：

```python
import logging

class Config:
    # 日志配置
    LOG_LEVEL = logging.INFO  # 日志级别
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 日志文件最大大小（字节）
    LOG_BACKUP_COUNT = 10  # 保留的日志备份文件数量
```

**日志文件位置**: `logs/proxy_fastapi.log`

**自动轮转机制**:
- 当日志文件达到 `LOG_MAX_BYTES` 大小时，自动创建新文件
- 旧文件会被重命名为 `proxy_fastapi.log.1`, `proxy_fastapi.log.2`, 等
- 保留最近的 `LOG_BACKUP_COUNT` 个备份文件
- 超出数量的旧文件会被自动删除

### 2. Gunicorn 访问和错误日志（Access & Error Logs）

Gunicorn 的访问日志和错误日志配置在 `logging_config.py` 中：

```python
# 日志轮转配置
LOG_MAX_BYTES = 8 * 1024 * 1024  # 8MB
LOG_BACKUP_COUNT = 10  # 最多保留10个备份文件
```

**日志文件位置**: 
- 访问日志：`logs/access_fastapi.log`
- 错误日志：`logs/error_fastapi.log`

**自动轮转机制**:
- 每个日志文件达到 **8MB** 时自动切割
- 最多保留 **10 个备份文件**
- 旧文件会被重命名为 `access_fastapi.log.1`, `access_fastapi.log.2`, 等
- 总计约 **88MB** 日志空间（8MB × 11 个文件）

如需调整轮转策略，请修改 `logging_config.py` 中的 `LOG_MAX_BYTES` 和 `LOG_BACKUP_COUNT` 参数。

### 日志级别选项

| 级别 | 值 | 说明 | 使用场景 |
|------|-----|------|----------|
| `logging.DEBUG` | 10 | 最详细的日志 | 开发和深度调试 |
| `logging.INFO` | 20 | 一般信息日志 | 生产环境监控（推荐） |
| `logging.WARNING` | 30 | 警告信息 | 生产环境（仅关键信息） |
| `logging.ERROR` | 40 | 错误信息 | 生产环境（仅错误） |
| `logging.CRITICAL` | 50 | 严重错误 | 生产环境（仅严重错误） |

### 示例配置

**应用日志配置（models/config.py）**:

```python
# 默认配置（推荐用于生产环境）
LOG_LEVEL = logging.INFO
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 10  # 总计约 110MB 日志空间

# 调试配置（临时排查问题）
LOG_LEVEL = logging.DEBUG
LOG_MAX_BYTES = 50 * 1024 * 1024  # 50MB
LOG_BACKUP_COUNT = 5  # 总计约 275MB 日志空间

# 生产环境精简配置（节省磁盘空间）
LOG_LEVEL = logging.WARNING
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB
LOG_BACKUP_COUNT = 3  # 总计约 20MB 日志空间
```

**Gunicorn 日志配置（logging_config.py）**:

```python
# 当前配置（适用于大多数场景）
LOG_MAX_BYTES = 8 * 1024 * 1024  # 8MB
LOG_BACKUP_COUNT = 10  # 总计约 88MB

# 高流量场景（需要更多日志历史）
LOG_MAX_BYTES = 8 * 1024 * 1024  # 8MB
LOG_BACKUP_COUNT = 20  # 总计约 168MB

# 低流量场景（节省磁盘空间）
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB
LOG_BACKUP_COUNT = 5  # 总计约 30MB
```

## 调试模式配置

```python
class Config:
    # 调试模式配置
    DEBUG_MODE = True  # 总体调试开关
    DEBUG_FULLY_ALLOWED_EXTENSIONS = True  # FULLY_ALLOWED_EXTENSIONS 详细调试
```

### DEBUG_MODE

控制全局调试信息的输出。

**启用时**:
- 输出详细的请求处理信息
- 显示性能指标
- 记录所有验证步骤

**建议**:
- 开发环境: `True`
- 生产环境: `False`

### DEBUG_FULLY_ALLOWED_EXTENSIONS

控制 FULLY_ALLOWED_EXTENSIONS 功能的详细日志。

**启用时输出的信息**:
```
🔍 DEBUG FULLY_ALLOWED_EXTENSIONS:
   配置值: ('.ts', '.webp')
   配置类型: <class 'tuple'>
   元素数量: 2
   请求路径: /video/test.ts
   小写路径: /video/test.ts
   skip_validation 结果: True
   - 扩展名 '.ts': True
   - 扩展名 '.webp': False
```

**建议**:
- 排查 FULLY_ALLOWED_EXTENSIONS 问题时: `True`
- 正常运行时: `False`

## 配置示例

### 开发环境配置

```python
# models/config.py

import logging

class Config:
    # 日志配置 - 详细日志用于开发调试
    LOG_LEVEL = logging.DEBUG
    LOG_MAX_BYTES = 50 * 1024 * 1024  # 50MB
    LOG_BACKUP_COUNT = 5
    
    # 调试模式 - 全部启用
    DEBUG_MODE = True
    DEBUG_FULLY_ALLOWED_EXTENSIONS = True
```

### 生产环境配置

```python
# models/config.py

import logging

class Config:
    # 日志配置 - 适度的信息日志
    LOG_LEVEL = logging.INFO
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 10
    
    # 调试模式 - 关闭以减少日志量
    DEBUG_MODE = False
    DEBUG_FULLY_ALLOWED_EXTENSIONS = False
```

### 问题排查配置（临时）

```python
# models/config.py

import logging

class Config:
    # 日志配置 - 详细日志用于排查问题
    LOG_LEVEL = logging.INFO  # 或 logging.DEBUG
    LOG_MAX_BYTES = 20 * 1024 * 1024  # 20MB
    LOG_BACKUP_COUNT = 10
    
    # 调试模式 - 启用需要调试的功能
    DEBUG_MODE = False  # 仅在需要时启用
    DEBUG_FULLY_ALLOWED_EXTENSIONS = True  # 排查扩展名问题
```

## 查看日志

### 实时查看日志

```bash
# 查看应用日志
tail -f logs/proxy_fastapi.log

# 查看访问日志（Gunicorn）
tail -f logs/access_fastapi.log

# 查看错误日志（Gunicorn）
tail -f logs/error_fastapi.log

# 查看最近 100 行
tail -n 100 logs/proxy_fastapi.log

# 搜索特定内容
grep "FULLY_ALLOWED_EXTENSIONS" logs/proxy_fastapi.log

# 搜索错误
grep -i "error" logs/error_fastapi.log
```

### 日志文件列表

```bash
# 查看所有日志文件
ls -lh logs/

# 示例输出：
# -rw-r--r-- 1 user user  10M Nov  9 10:30 proxy_fastapi.log
# -rw-r--r-- 1 user user  10M Nov  9 10:00 proxy_fastapi.log.1
# -rw-r--r-- 1 user user  10M Nov  9 09:30 proxy_fastapi.log.2
# -rw-r--r-- 1 user user   8M Nov  9 10:30 access_fastapi.log
# -rw-r--r-- 1 user user   8M Nov  9 10:00 access_fastapi.log.1
# -rw-r--r-- 1 user user   8M Nov  9 09:30 access_fastapi.log.2
# -rw-r--r-- 1 user user   1M Nov  9 10:30 error_fastapi.log
# ...
```

## 注意事项

1. **磁盘空间**: 确保日志目录有足够空间
   - 应用日志: `LOG_MAX_BYTES × (LOG_BACKUP_COUNT + 1)` ≈ 110MB (默认)
   - 访问日志: `8MB × 11` ≈ 88MB
   - 错误日志: `8MB × 11` ≈ 88MB
   - 总计约 **286MB**

2. **性能影响**: 
   - `DEBUG` 级别会产生大量日志，可能影响性能
   - 生产环境建议使用 `INFO` 或更高级别

3. **日志轮转**: 
   - 自动进行，无需手动管理
   - 旧日志会被自动删除
   - 访问日志和错误日志每 8MB 自动切割

4. **调试后记得关闭**: 
   - 排查问题后，记得将 DEBUG 标志改回 `False`
   - 避免产生过多日志影响性能

## 相关文档

- [故障排查指南](TROUBLESHOOTING_CN.md)
- [诊断工具说明](DIAGNOSE_README.md)
- [完整文档](docs/FULLY_ALLOWED_EXTENSIONS.md)
