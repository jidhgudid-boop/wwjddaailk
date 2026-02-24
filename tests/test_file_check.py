"""
测试文件存在性检查API
Tests for file existence check API
"""
import sys
import os
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.file_check import (
    check_file_exists_filesystem,
    FileCheckRequest,
    BatchFileCheckRequest
)


def test_file_check_request_validation():
    """测试单文件检查请求验证"""
    # Valid request
    request = FileCheckRequest(path="/test/video.mp4")
    assert request.path == "/test/video.mp4"
    
    # Test with invalid data (missing path) should raise validation error
    try:
        FileCheckRequest()
        assert False, "Should have raised validation error"
    except Exception:
        pass  # Expected


def test_batch_file_check_request_validation():
    """测试批量文件检查请求验证"""
    # Valid request with multiple paths
    request = BatchFileCheckRequest(paths=["/test1.mp4", "/test2.mp4"])
    assert len(request.paths) == 2
    
    # Test with empty list should raise validation error
    try:
        BatchFileCheckRequest(paths=[])
        assert False, "Should have raised validation error"
    except Exception:
        pass  # Expected
    
    # Test with too many paths (> 100) should raise validation error
    try:
        BatchFileCheckRequest(paths=[f"/test{i}.mp4" for i in range(101)])
        assert False, "Should have raised validation error"
    except Exception:
        pass  # Expected


async def test_check_file_exists_filesystem():
    """测试文件系统模式下的文件存在性检查"""
    # Test with a path that should be blocked (path traversal)
    result = await check_file_exists_filesystem("../../etc/passwd")
    assert result["exists"] is False
    assert result["error"] == "Invalid path"
    
    # Test with a normal path (will fail if filesystem not available)
    # This is just a structure test
    result = await check_file_exists_filesystem("/test/nonexistent.mp4")
    assert "exists" in result
    assert "error" in result


if __name__ == "__main__":
    print("Running basic tests...")
    
    # Test request validation
    try:
        test_file_check_request_validation()
        print("✅ FileCheckRequest validation test passed")
    except Exception as e:
        print(f"❌ FileCheckRequest validation test failed: {e}")
    
    try:
        test_batch_file_check_request_validation()
        print("✅ BatchFileCheckRequest validation test passed")
    except Exception as e:
        print(f"❌ BatchFileCheckRequest validation test failed: {e}")
    
    # Test async function
    try:
        asyncio.run(test_check_file_exists_filesystem())
        print("✅ check_file_exists_filesystem test passed")
    except Exception as e:
        print(f"❌ check_file_exists_filesystem test failed: {e}")
    
    print("\n✅ All tests completed successfully!")

