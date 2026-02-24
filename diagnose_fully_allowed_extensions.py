#!/usr/bin/env python3
"""
诊断 FULLY_ALLOWED_EXTENSIONS 配置问题
Diagnose FULLY_ALLOWED_EXTENSIONS configuration issues

使用方法 / Usage:
    python diagnose_fully_allowed_extensions.py
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("FULLY_ALLOWED_EXTENSIONS 配置诊断工具")
print("FULLY_ALLOWED_EXTENSIONS Configuration Diagnostic Tool")
print("=" * 80)

# 步骤 1: 尝试导入配置
print("\n步骤 1: 加载配置文件")
print("-" * 80)
try:
    from models.config import config
    print("✅ 配置文件加载成功")
except Exception as e:
    print(f"❌ 配置文件加载失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤 2: 检查配置值
print("\n步骤 2: 检查 FULLY_ALLOWED_EXTENSIONS 配置")
print("-" * 80)

try:
    fully_allowed = config.FULLY_ALLOWED_EXTENSIONS
    print(f"✅ FULLY_ALLOWED_EXTENSIONS 存在")
    print(f"   值: {fully_allowed}")
    print(f"   类型: {type(fully_allowed)}")
    print(f"   长度: {len(fully_allowed)}")
    
    # 检查每个元素
    print(f"\n   元素详情:")
    for i, ext in enumerate(fully_allowed):
        print(f"   [{i}] '{ext}'")
        print(f"       类型: {type(ext)}")
        print(f"       长度: {len(ext)}")
        print(f"       点的数量: {ext.count('.')}")
        
        # 检查是否有字符串连接问题
        if ext.count('.') > 1:
            print(f"       ⚠️  警告: 此扩展名包含多个点，可能是字符串连接的结果!")
        else:
            print(f"       ✅ 格式正确")
    
except AttributeError:
    print("❌ FULLY_ALLOWED_EXTENSIONS 配置不存在")
    sys.exit(1)
except Exception as e:
    print(f"❌ 检查配置时出错: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤 3: 测试 str.endswith() 功能
print("\n步骤 3: 测试 str.endswith() 功能")
print("-" * 80)

test_paths = [
    "/video/segment.ts",
    "/image/preview.webp",
    "/video/playlist.m3u8",
    "/script.php",
    "/static/style.css"
]

print("测试文件路径匹配:")
for path in test_paths:
    try:
        matches = path.lower().endswith(config.FULLY_ALLOWED_EXTENSIONS)
        status = "✅ 匹配" if matches else "❌ 不匹配"
        print(f"  {status}: {path}")
    except Exception as e:
        print(f"  ❌ 错误: {path} - {e}")

# 步骤 4: 检查相关配置
print("\n步骤 4: 检查相关配置")
print("-" * 80)

print(f"ENABLE_STATIC_FILE_IP_ONLY_CHECK: {config.ENABLE_STATIC_FILE_IP_ONLY_CHECK}")
print(f"DEBUG_MODE: {getattr(config, 'DEBUG_MODE', 'Not defined')}")
print(f"DEBUG_FULLY_ALLOWED_EXTENSIONS: {getattr(config, 'DEBUG_FULLY_ALLOWED_EXTENSIONS', 'Not defined')}")

# 步骤 5: 检查配置文件源代码
print("\n步骤 5: 检查配置文件源代码")
print("-" * 80)

config_file = os.path.join(os.path.dirname(__file__), 'models', 'config.py')
try:
    with open(config_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 查找 FULLY_ALLOWED_EXTENSIONS 定义
    in_definition = False
    definition_lines = []
    
    for i, line in enumerate(lines, 1):
        if 'FULLY_ALLOWED_EXTENSIONS' in line and '=' in line:
            in_definition = True
            definition_lines.append((i, line.rstrip()))
        elif in_definition:
            definition_lines.append((i, line.rstrip()))
            if ')' in line and not line.strip().endswith(','):
                # 可能是定义结束
                if line.strip() == ')':
                    break
    
    print("配置文件中的定义 (models/config.py):")
    for line_num, line_text in definition_lines:
        print(f"  {line_num:4d}: {line_text}")
    
except Exception as e:
    print(f"❌ 读取配置文件失败: {e}")

# 步骤 6: 模拟添加新扩展名
print("\n步骤 6: 模拟添加新扩展名测试")
print("-" * 80)

test_configs = [
    ("单个扩展名", """
FULLY_ALLOWED_EXTENSIONS = (
    '.ts',
)
"""),
    ("两个扩展名", """
FULLY_ALLOWED_EXTENSIONS = (
    '.ts',
    '.webp',
)
"""),
    ("三个扩展名", """
FULLY_ALLOWED_EXTENSIONS = (
    '.ts',
    '.webp',
    '.php',
)
"""),
]

for name, test_code in test_configs:
    namespace = {}
    try:
        exec(test_code, namespace)
        result = namespace['FULLY_ALLOWED_EXTENSIONS']
        print(f"✅ {name}: {result} (长度: {len(result)})")
    except Exception as e:
        print(f"❌ {name}: 错误 - {e}")

# 步骤 7: 总结和建议
print("\n" + "=" * 80)
print("诊断总结 / Summary")
print("=" * 80)

issues = []

# 检查类型
if not isinstance(config.FULLY_ALLOWED_EXTENSIONS, tuple):
    issues.append(f"❌ FULLY_ALLOWED_EXTENSIONS 类型错误: {type(config.FULLY_ALLOWED_EXTENSIONS)}, 应该是 tuple")

# 检查字符串连接
for ext in config.FULLY_ALLOWED_EXTENSIONS:
    if ext.count('.') > 1:
        issues.append(f"❌ 扩展名 '{ext}' 可能是字符串连接的结果")

if issues:
    print("\n发现的问题:")
    for issue in issues:
        print(f"  {issue}")
    
    print("\n建议:")
    print("  1. 检查 models/config.py 中的 FULLY_ALLOWED_EXTENSIONS 定义")
    print("  2. 确保每个元素后都有逗号 (,)")
    print("  3. 清除 Python 缓存:")
    print("     find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null")
    print("     find . -name '*.pyc' -delete")
    print("  4. 重启服务器")
else:
    print("\n✅ 所有检查通过!")
    print("   FULLY_ALLOWED_EXTENSIONS 配置正确")
    
    print("\n如果仍然遇到 Internal Server Error:")
    print("  1. 启用调试模式: 在 models/config.py 中设置")
    print("     DEBUG_FULLY_ALLOWED_EXTENSIONS = True")
    print("  2. 重启服务器并查看日志中的详细调试信息")
    print("  3. 检查服务器日志文件获取完整的错误堆栈信息")

print("\n" + "=" * 80)
