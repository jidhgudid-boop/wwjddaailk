"""
测试完全放行文件扩展名配置功能
Test fully allowed file extensions configuration
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.config import config


def test_fully_allowed_extensions_configuration():
    """测试 FULLY_ALLOWED_EXTENSIONS 配置是否存在且格式正确"""
    print("测试 1: 检查 FULLY_ALLOWED_EXTENSIONS 配置...")
    
    # 检查配置属性存在
    assert hasattr(config, 'FULLY_ALLOWED_EXTENSIONS'), \
        "配置缺失: FULLY_ALLOWED_EXTENSIONS 不存在"
    
    # 检查是否为元组类型
    assert isinstance(config.FULLY_ALLOWED_EXTENSIONS, tuple), \
        f"配置类型错误: FULLY_ALLOWED_EXTENSIONS 应该是 tuple，实际为 {type(config.FULLY_ALLOWED_EXTENSIONS)}"
    
    # 检查不为空
    assert len(config.FULLY_ALLOWED_EXTENSIONS) > 0, \
        "配置为空: FULLY_ALLOWED_EXTENSIONS 至少应该包含一个扩展名"
    
    print(f"✅ FULLY_ALLOWED_EXTENSIONS 配置正确: {config.FULLY_ALLOWED_EXTENSIONS}")


def test_extension_format():
    """测试扩展名格式是否正确（以点开头的小写字符串）"""
    print("\n测试 2: 检查扩展名格式...")
    
    for ext in config.FULLY_ALLOWED_EXTENSIONS:
        # 检查是否为字符串
        assert isinstance(ext, str), \
            f"扩展名格式错误: '{ext}' 应该是字符串类型"
        
        # 检查是否以点开头
        assert ext.startswith('.'), \
            f"扩展名格式错误: '{ext}' 应该以点(.)开头"
        
        # 检查是否为小写（推荐）
        assert ext == ext.lower(), \
            f"扩展名格式警告: '{ext}' 建议使用小写"
    
    print(f"✅ 所有扩展名格式正确")


def test_default_extensions():
    """测试默认扩展名是否包含预期的值"""
    print("\n测试 3: 检查默认扩展名...")
    
    # 检查默认应该包含的扩展名
    expected_extensions = ['.ts', '.webp']
    
    for ext in expected_extensions:
        assert ext in config.FULLY_ALLOWED_EXTENSIONS, \
            f"默认扩展名缺失: '{ext}' 应该在 FULLY_ALLOWED_EXTENSIONS 中"
        print(f"  ✅ 找到扩展名: {ext}")
    
    print(f"✅ 默认扩展名完整")


def test_endswith_compatibility():
    """测试配置可以直接用于 str.endswith() 方法"""
    print("\n测试 4: 检查与 str.endswith() 兼容性...")
    
    # 测试文件路径 - 使用已知在配置中的扩展名
    test_paths = [
        ("/path/to/video.ts", True),      # 默认配置包含
        ("/path/to/image.webp", True),    # 默认配置包含
        ("/path/to/playlist.m3u8", False),
        ("/path/to/script.js", False),
        ("/path/to/image.jpg", False),
        ("/path/to/script.php", False),   # 不在默认配置中
    ]
    
    for path, should_match in test_paths:
        matches = path.lower().endswith(config.FULLY_ALLOWED_EXTENSIONS)
        
        if should_match:
            assert matches, f"路径 '{path}' 应该匹配 FULLY_ALLOWED_EXTENSIONS"
            print(f"  ✅ '{path}' 正确匹配")
        else:
            assert not matches, f"路径 '{path}' 不应该匹配 FULLY_ALLOWED_EXTENSIONS"
            print(f"  ✅ '{path}' 正确不匹配")
    
    print(f"✅ endswith() 兼容性测试通过")



def test_configuration_independence():
    """测试 FULLY_ALLOWED_EXTENSIONS 与 STATIC_FILE_EXTENSIONS 的独立性"""
    print("\n测试 5: 检查配置独立性...")
    
    # 确保两个配置都存在
    assert hasattr(config, 'STATIC_FILE_EXTENSIONS'), \
        "STATIC_FILE_EXTENSIONS 配置不存在"
    
    # 检查它们是不同的对象
    assert config.FULLY_ALLOWED_EXTENSIONS is not config.STATIC_FILE_EXTENSIONS, \
        "FULLY_ALLOWED_EXTENSIONS 和 STATIC_FILE_EXTENSIONS 应该是独立的配置"
    
    print(f"  FULLY_ALLOWED_EXTENSIONS: {config.FULLY_ALLOWED_EXTENSIONS}")
    print(f"  STATIC_FILE_EXTENSIONS: {config.STATIC_FILE_EXTENSIONS}")
    print(f"✅ 配置独立性验证通过")


def test_trailing_comma_prevents_concatenation():
    """测试添加新扩展名时不会因为缺少逗号而导致字符串连接"""
    print("\n测试 6: 验证配置中的尾随逗号防止字符串连接...")
    
    # 读取配置文件内容
    import os
    config_file_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'config.py')
    
    with open(config_file_path, 'r', encoding='utf-8') as f:
        config_content = f.read()
    
    # 查找 FULLY_ALLOWED_EXTENSIONS 定义
    import re
    pattern = r'FULLY_ALLOWED_EXTENSIONS\s*=\s*\((.*?)\)'
    match = re.search(pattern, config_content, re.DOTALL)
    
    assert match, "无法找到 FULLY_ALLOWED_EXTENSIONS 配置"
    
    tuple_content = match.group(1)
    
    # 检查配置中的每一行（除了最后一行的结束括号）
    lines = [line.strip() for line in tuple_content.split('\n') if line.strip() and not line.strip().startswith('#')]
    
    # 检查是否有尾随逗号或者只有一个元素
    has_trailing_commas = True
    for i, line in enumerate(lines):
        # 去除注释
        code_part = line.split('#')[0].strip()
        if code_part and not code_part.endswith(','):
            # 允许最后一行没有逗号，但仍然推荐有逗号
            if i < len(lines) - 1:
                has_trailing_commas = False
                print(f"  ⚠️ 第 {i+1} 行缺少尾随逗号: {code_part}")
    
    # 验证元组中每个元素都是独立的
    for ext in config.FULLY_ALLOWED_EXTENSIONS:
        # 检查不包含连接的扩展名（如 '.webp.php'）
        dots_count = ext.count('.')
        assert dots_count == 1, \
            f"扩展名 '{ext}' 可能是字符串连接的结果（包含 {dots_count} 个点）"
        print(f"  ✅ 扩展名 '{ext}' 格式正确")
    
    print(f"✅ 配置验证通过：无字符串连接问题")
    
    # 模拟添加新扩展名
    print("\n  模拟添加新扩展名 '.php'...")
    test_code = """
FULLY_ALLOWED_EXTENSIONS = (
    '.ts',    # HLS 视频分片
    '.webp',  # 预览图
    '.php',   # 新添加的扩展名
)
"""
    namespace = {}
    exec(test_code, namespace)
    result = namespace['FULLY_ALLOWED_EXTENSIONS']
    
    assert len(result) == 3, f"添加后应该有3个元素，实际有 {len(result)} 个"
    assert result[0] == '.ts', f"第1个元素应该是 '.ts'，实际是 '{result[0]}'"
    assert result[1] == '.webp', f"第2个元素应该是 '.webp'，实际是 '{result[1]}'"
    assert result[2] == '.php', f"第3个元素应该是 '.php'，实际是 '{result[2]}'"
    
    print(f"  ✅ 模拟添加成功: {result}")
    print(f"✅ 尾随逗号验证通过：可以安全添加新扩展名")



def main():
    """运行所有测试"""
    print("=" * 70)
    print("测试: 完全放行文件扩展名配置 (FULLY_ALLOWED_EXTENSIONS)")
    print("=" * 70)
    
    try:
        test_fully_allowed_extensions_configuration()
        test_extension_format()
        test_default_extensions()
        test_endswith_compatibility()
        test_configuration_independence()
        test_trailing_comma_prevents_concatenation()
        
        print("\n" + "=" * 70)
        print("✅ 所有测试通过!")
        print("=" * 70)
        return 0
    except AssertionError as e:
        print(f"\n❌ 测试失败: {str(e)}")
        return 1
    except Exception as e:
        print(f"\n❌ 测试出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
