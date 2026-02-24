# FULLY_ALLOWED_EXTENSIONS 故障排查指南

## 快速诊断

如果您遇到 "Internal Server Error" 或者 FULLY_ALLOWED_EXTENSIONS 无法正常工作，请按以下步骤操作：

### 步骤 1: 运行诊断工具

```bash
cd /path/to/YuemPyScripts/Server/FileProxy
python diagnose_fully_allowed_extensions.py
```

这个工具会自动检查：
- ✅ 配置文件语法是否正确
- ✅ 是否存在字符串连接问题
- ✅ 元组类型和长度是否正确
- ✅ 文件匹配功能是否正常

### 步骤 2: 启用调试模式

在 `models/config.py` 中设置：

```python
# 日志配置
LOG_LEVEL = logging.INFO  # 或 logging.DEBUG 获取更详细的日志
LOG_MAX_BYTES = 10 * 1024 * 1024  # 日志文件最大 10MB
LOG_BACKUP_COUNT = 10  # 保留 10 个备份文件

# 调试模式配置（用于排查问题，生产环境应设为 False）
DEBUG_MODE = True  # 设为 True 启用详细的调试日志
DEBUG_FULLY_ALLOWED_EXTENSIONS = True  # 设为 True 启用详细调试信息
```

**日志文件位置**: `logs/proxy_fastapi.log`
- 自动轮转：每个文件最大 10MB
- 保留最多 10 个备份文件
- 总计最多约 110MB 日志存储空间

### 步骤 3: 重启服务器

```bash
# 完全停止服务器
# 清除 Python 缓存
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete

# 启动服务器
```

### 步骤 4: 查看日志

启用调试模式后，每次请求都会在日志中显示：

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

## 常见问题

### Q1: 配置只支持一个扩展名，两个就报错？

**A**: 配置语法需要每个元素后都加逗号：

```python
# ❌ 错误 - 缺少逗号
FULLY_ALLOWED_EXTENSIONS = (
    '.ts',
    '.webp'   # 缺少逗号！
)

# ✅ 正确 - 有逗号
FULLY_ALLOWED_EXTENSIONS = (
    '.ts',
    '.webp',  # 有逗号
)
```

### Q2: 诊断工具显示配置正确，但运行时还是错误？

**A**: 可能是缓存问题：

1. 清除 Python 字节码缓存
2. 完全重启服务器（不要只是 reload）
3. 启用 DEBUG_FULLY_ALLOWED_EXTENSIONS 查看运行时的实际值

### Q3: 如何添加更多扩展名？

**A**: 只需添加新行，确保每行都有逗号：

```python
FULLY_ALLOWED_EXTENSIONS = (
    '.ts',      # HLS 视频分片
    '.webp',    # 预览图
    '.php',     # PHP 文件
    '.mp4',     # MP4 视频
)
```

## 确认配置正确

运行此命令确认配置已正确加载：

```bash
cd Server/FileProxy
python -c "
from models.config import config
print(f'FULLY_ALLOWED_EXTENSIONS = {config.FULLY_ALLOWED_EXTENSIONS}')
print(f'类型: {type(config.FULLY_ALLOWED_EXTENSIONS)}')
print(f'长度: {len(config.FULLY_ALLOWED_EXTENSIONS)}')
"
```

应该输出：
```
FULLY_ALLOWED_EXTENSIONS = ('.ts', '.webp')
类型: <class 'tuple'>
长度: 2
```

## 获取帮助

如果以上步骤都无法解决问题，请：

1. 运行诊断工具并保存输出
2. 启用 DEBUG_FULLY_ALLOWED_EXTENSIONS 并收集日志
3. 提供完整的错误堆栈信息
4. 在 GitHub Issue 中附上以上信息

## 相关文件

- 诊断工具: `diagnose_fully_allowed_extensions.py`
- 配置文件: `models/config.py`
- 路由文件: `routes/proxy.py`
- 完整文档: `docs/FULLY_ALLOWED_EXTENSIONS.md`
- 测试文件: `tests/test_fully_allowed_extensions.py`
