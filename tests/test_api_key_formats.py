"""
测试API Key认证的多种格式
Tests for API key authentication with multiple formats
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helpers import validate_api_key


def test_validate_api_key_with_bearer():
    """测试使用Bearer前缀的标准格式"""
    api_key = "F2UkWEJZRBxC7"
    
    # 标准Bearer格式应该通过
    assert validate_api_key(f"Bearer {api_key}", api_key) == True
    print("✅ Bearer format validation passed")
    

def test_validate_api_key_without_bearer():
    """测试不使用Bearer前缀的简化格式"""
    api_key = "F2UkWEJZRBxC7"
    
    # 简化格式（直接是API key）应该通过
    assert validate_api_key(api_key, api_key) == True
    print("✅ Direct API key format validation passed")


def test_validate_api_key_invalid():
    """测试无效的API Key"""
    api_key = "F2UkWEJZRBxC7"
    
    # 错误的API key应该失败
    assert validate_api_key("WrongKey", api_key) == False
    assert validate_api_key("Bearer WrongKey", api_key) == False
    print("✅ Invalid API key rejection passed")


def test_validate_api_key_none():
    """测试空值或None"""
    api_key = "F2UkWEJZRBxC7"
    
    # None 或空字符串应该失败
    assert validate_api_key(None, api_key) == False
    assert validate_api_key("", api_key) == False
    print("✅ None/empty validation passed")


def test_validate_api_key_case_sensitive():
    """测试API Key是否区分大小写"""
    api_key = "F2UkWEJZRBxC7"
    
    # API key应该区分大小写
    assert validate_api_key("f2ukwejzrbxc7", api_key) == False
    assert validate_api_key("Bearer f2ukwejzrbxc7", api_key) == False
    print("✅ Case sensitivity validation passed")


def test_validate_api_key_with_extra_spaces():
    """测试带有额外空格的情况"""
    api_key = "F2UkWEJZRBxC7"
    
    # Bearer后带多个空格应该失败（严格匹配）
    assert validate_api_key("Bearer  " + api_key, api_key) == False
    # Bearer前带空格应该失败
    assert validate_api_key(" Bearer " + api_key, api_key) == False
    print("✅ Extra spaces validation passed")


if __name__ == "__main__":
    print("Running API key authentication format tests...\n")
    
    try:
        test_validate_api_key_with_bearer()
        test_validate_api_key_without_bearer()
        test_validate_api_key_invalid()
        test_validate_api_key_none()
        test_validate_api_key_case_sensitive()
        test_validate_api_key_with_extra_spaces()
        print("\n✅ All API key format tests passed successfully!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
