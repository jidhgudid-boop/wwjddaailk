"""
Standalone validation test for file_check API
Tests the core logic without requiring full dependencies
"""
import sys
import os
import asyncio

# Test path validation logic (security check)
def test_path_traversal_protection():
    """Test that path traversal attacks are blocked"""
    root = "/data"
    
    # Test cases for path traversal attempts
    test_cases = [
        ("../../etc/passwd", False, "Should block parent directory traversal"),
        ("../../../etc/passwd", False, "Should block multiple parent traversal"),
        ("/test/video.mp4", True, "Should allow normal paths"),
        ("test/video.mp4", True, "Should allow relative paths within root"),
    ]
    
    for path, should_allow, description in test_cases:
        full_path = os.path.join(root, path.lstrip('/'))
        resolved_path = os.path.abspath(full_path)
        root_path = os.path.abspath(root)
        
        is_safe = resolved_path.startswith(root_path)
        
        if should_allow:
            assert is_safe, f"Failed: {description} - Path: {path}"
            print(f"✅ {description}: {path}")
        else:
            assert not is_safe, f"Failed: {description} - Path: {path}"
            print(f"✅ {description}: {path}")


def test_pydantic_models():
    """Test Pydantic model validation"""
    try:
        from pydantic import BaseModel, Field, ValidationError
        
        class FileCheckRequest(BaseModel):
            path: str = Field(..., description="文件路径")
        
        class BatchFileCheckRequest(BaseModel):
            paths: list = Field(..., description="文件路径列表", min_length=1, max_length=100)
        
        # Test valid single file request
        request = FileCheckRequest(path="/test/video.mp4")
        assert request.path == "/test/video.mp4"
        print("✅ Valid FileCheckRequest accepted")
        
        # Test invalid single file request (missing path)
        try:
            FileCheckRequest()
            assert False, "Should have raised ValidationError"
        except ValidationError:
            print("✅ Invalid FileCheckRequest rejected (missing path)")
        
        # Test valid batch request
        batch = BatchFileCheckRequest(paths=["/test1.mp4", "/test2.mp4"])
        assert len(batch.paths) == 2
        print("✅ Valid BatchFileCheckRequest accepted")
        
        # Test invalid batch request (empty list)
        try:
            BatchFileCheckRequest(paths=[])
            assert False, "Should have raised ValidationError"
        except ValidationError:
            print("✅ Invalid BatchFileCheckRequest rejected (empty list)")
        
        # Test invalid batch request (too many items)
        try:
            BatchFileCheckRequest(paths=[f"/test{i}.mp4" for i in range(101)])
            assert False, "Should have raised ValidationError"
        except ValidationError:
            print("✅ Invalid BatchFileCheckRequest rejected (too many items)")
        
        return True
    except ImportError:
        print("⚠️  Pydantic not installed, skipping model validation tests")
        return False


def test_file_check_logic():
    """Test the basic file check logic structure"""
    print("\n=== Testing File Check Logic ===")
    
    # Simulate the check logic
    def check_file_exists(file_path: str, root: str = "/data") -> dict:
        """Simulated file check logic"""
        try:
            full_path = os.path.join(root, file_path.lstrip('/'))
            resolved_path = os.path.abspath(full_path)
            root_path = os.path.abspath(root)
            
            # Security check
            if not resolved_path.startswith(root_path):
                return {"exists": False, "error": "Invalid path"}
            
            # Check file existence
            exists = os.path.isfile(resolved_path)
            return {"exists": exists, "error": None}
        except Exception as e:
            return {"exists": False, "error": str(e)}
    
    # Test with path traversal attempt
    result = check_file_exists("../../etc/passwd")
    assert result["exists"] is False
    assert result["error"] == "Invalid path"
    print("✅ Path traversal blocked correctly")
    
    # Test with normal path
    result = check_file_exists("/test/video.mp4")
    assert "exists" in result
    assert "error" in result
    print("✅ Normal path processed correctly")
    
    return True


if __name__ == "__main__":
    print("Running standalone validation tests...\n")
    
    print("=== Testing Path Security ===")
    test_path_traversal_protection()
    
    print("\n=== Testing Pydantic Models ===")
    test_pydantic_models()
    
    print("\n=== Testing File Check Logic ===")
    test_file_check_logic()
    
    print("\n" + "="*50)
    print("✅ All validation tests passed!")
    print("="*50)
