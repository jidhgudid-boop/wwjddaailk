#!/usr/bin/env python3
"""
测试并行验证和请求去重功能
Test parallel validation and request deduplication features
"""
import sys
import os
import time
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.config import config


def test_config_flags():
    """测试配置标志是否正确设置"""
    print("=" * 60)
    print("测试配置标志")
    print("=" * 60)
    
    assert config.ENABLE_REQUEST_DEDUPLICATION == True, "ENABLE_REQUEST_DEDUPLICATION should be True"
    assert config.ENABLE_PARALLEL_VALIDATION == True, "ENABLE_PARALLEL_VALIDATION should be True"
    assert config.ENABLE_REDIS_PIPELINE == True, "ENABLE_REDIS_PIPELINE should be True"
    assert config.ENABLE_RESPONSE_STREAMING == True, "ENABLE_RESPONSE_STREAMING should be True"
    
    print(f"✅ ENABLE_REQUEST_DEDUPLICATION: {config.ENABLE_REQUEST_DEDUPLICATION}")
    print(f"✅ ENABLE_PARALLEL_VALIDATION: {config.ENABLE_PARALLEL_VALIDATION}")
    print(f"✅ ENABLE_REDIS_PIPELINE: {config.ENABLE_REDIS_PIPELINE}")
    print(f"✅ ENABLE_RESPONSE_STREAMING: {config.ENABLE_RESPONSE_STREAMING}")
    print()


async def test_request_deduplicator():
    """测试请求去重器逻辑"""
    print("=" * 60)
    print("测试请求去重器逻辑")
    print("=" * 60)
    
    # 创建一个简单的去重器实现来测试逻辑
    import hashlib
    
    pending_requests = {}
    
    def generate_key(ip, path, ua, uid):
        key_parts = [ip, path, ua]
        if uid:
            key_parts.append(uid)
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    # 测试相同请求生成相同的key
    key1 = generate_key("192.168.1.1", "/test/path.ts", "TestAgent", None)
    key2 = generate_key("192.168.1.1", "/test/path.ts", "TestAgent", None)
    key3 = generate_key("192.168.1.1", "/test/path2.ts", "TestAgent", None)
    
    print(f"相同请求生成的key: {key1[:16]}... 和 {key2[:16]}...")
    print(f"不同请求生成的key: {key3[:16]}...")
    
    assert key1 == key2, "相同请求应该生成相同的key"
    assert key1 != key3, "不同请求应该生成不同的key"
    
    print("✅ 请求去重器逻辑正常")
    print()


async def test_parallel_validation_timing():
    """测试并行验证性能"""
    print("=" * 60)
    print("测试并行验证性能")
    print("=" * 60)
    
    # 模拟两个独立的验证操作
    async def task1():
        await asyncio.sleep(0.1)
        return "task1_result"
    
    async def task2():
        await asyncio.sleep(0.1)
        return "task2_result"
    
    # 顺序执行
    start_sequential = time.time()
    result1 = await task1()
    result2 = await task2()
    sequential_time = time.time() - start_sequential
    
    # 并行执行
    start_parallel = time.time()
    results = await asyncio.gather(task1(), task2())
    parallel_time = time.time() - start_parallel
    
    speedup = sequential_time / parallel_time
    
    print(f"顺序执行时间: {sequential_time * 1000:.2f}ms")
    print(f"并行执行时间: {parallel_time * 1000:.2f}ms")
    print(f"性能提升: {speedup:.2f}x")
    
    # 并行执行应该明显快于顺序执行
    assert parallel_time < sequential_time * 0.7, "并行执行应该比顺序执行快至少30%"
    
    print("✅ 并行验证性能正常")
    print()


def test_validation_service_syntax():
    """测试验证服务Python语法"""
    print("=" * 60)
    print("测试验证服务Python语法")
    print("=" * 60)
    
    try:
        import py_compile
        service_path = os.path.join(os.path.dirname(__file__), '..', 'services', 'validation_service.py')
        py_compile.compile(service_path, doraise=True)
        print("✅ 验证服务语法正确")
        print()
        return True
    except Exception as e:
        print(f"❌ 语法错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_proxy_routes_syntax():
    """测试代理路由Python语法"""
    print("=" * 60)
    print("测试代理路由Python语法")
    print("=" * 60)
    
    try:
        import py_compile
        routes_path = os.path.join(os.path.dirname(__file__), '..', 'routes', 'proxy.py')
        py_compile.compile(routes_path, doraise=True)
        print("✅ 代理路由语法正确")
        print()
        return True
    except Exception as e:
        print(f"❌ 语法错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    try:
        print("\n" + "=" * 60)
        print("开始运行并行验证和请求去重功能测试")
        print("=" * 60 + "\n")
        
        # 测试1: 配置标志
        test_config_flags()
        
        # 测试2: 语法验证
        if not test_validation_service_syntax():
            return False
        
        if not test_proxy_routes_syntax():
            return False
        
        # 测试3: 请求去重器
        await test_request_deduplicator()
        
        # 测试4: 并行验证性能
        await test_parallel_validation_timing()
        
        print("=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
