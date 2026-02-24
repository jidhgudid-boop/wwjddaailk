# FULLY_ALLOWED_EXTENSIONS 诊断工具

## 概述

`diagnose_fully_allowed_extensions.py` 是一个诊断工具，用于检查和验证 `FULLY_ALLOWED_EXTENSIONS` 配置是否正确。

## 使用方法

```bash
cd /home/runner/work/YuemPyScripts/YuemPyScripts/Server/FileProxy
python diagnose_fully_allowed_extensions.py
```

## 检查项目

该工具会自动执行以下检查：

1. **配置文件加载**: 验证 `models/config.py` 是否能正确加载
2. **配置值检查**: 检查 `FULLY_ALLOWED_EXTENSIONS` 的类型、长度和内容
3. **字符串连接检测**: 检测是否存在 Python 字符串字面量连接问题
4. **功能测试**: 测试 `str.endswith()` 是否正常工作
5. **源代码检查**: 显示配置文件中的实际定义
6. **模拟测试**: 模拟添加多个扩展名的场景

## 输出示例

```
================================================================================
FULLY_ALLOWED_EXTENSIONS 配置诊断工具
================================================================================

步骤 1: 加载配置文件
--------------------------------------------------------------------------------
✅ 配置文件加载成功

步骤 2: 检查 FULLY_ALLOWED_EXTENSIONS 配置
--------------------------------------------------------------------------------
✅ FULLY_ALLOWED_EXTENSIONS 存在
   值: ('.ts', '.webp')
   类型: <class 'tuple'>
   长度: 2

   元素详情:
   [0] '.ts'
       类型: <class 'str'>
       长度: 3
       点的数量: 1
       ✅ 格式正确
   [1] '.webp'
       类型: <class 'str'>
       长度: 5
       点的数量: 1
       ✅ 格式正确

...

================================================================================
诊断总结 / Summary
================================================================================

✅ 所有检查通过!
   FULLY_ALLOWED_EXTENSIONS 配置正确
```

## 如果发现问题

如果诊断工具发现问题，它会提供具体的建议：

1. 检查 `models/config.py` 中的配置定义
2. 确保每个元素后都有逗号
3. 清除 Python 缓存
4. 重启服务器

## 启用调试模式

如果诊断工具显示配置正确，但仍然遇到运行时错误，请启用调试模式：

在 `models/config.py` 中设置：

```python
# 调试模式配置
DEBUG_FULLY_ALLOWED_EXTENSIONS = True
```

然后重启服务器并检查日志中的详细调试信息。

## 相关文档

- [FULLY_ALLOWED_EXTENSIONS 完整文档](docs/FULLY_ALLOWED_EXTENSIONS.md)
- [测试文件](tests/test_fully_allowed_extensions.py)
