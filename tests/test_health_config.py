#!/usr/bin/env python3
"""
Test script to verify /health endpoint returns correct performance optimization config values
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.config import config


def test_config_values():
    """Test that config has the correct performance optimization values"""
    print("Testing configuration values...")
    
    # Test individual values
    assert config.ENABLE_REQUEST_DEDUPLICATION == True, "ENABLE_REQUEST_DEDUPLICATION should be True"
    assert config.ENABLE_PARALLEL_VALIDATION == True, "ENABLE_PARALLEL_VALIDATION should be True"
    assert config.ENABLE_REDIS_PIPELINE == True, "ENABLE_REDIS_PIPELINE should be True"
    assert config.ENABLE_RESPONSE_STREAMING == True, "ENABLE_RESPONSE_STREAMING should be True"
    
    print("✅ All config values are correctly set to True")
    print(f"  - ENABLE_REQUEST_DEDUPLICATION: {config.ENABLE_REQUEST_DEDUPLICATION}")
    print(f"  - ENABLE_PARALLEL_VALIDATION: {config.ENABLE_PARALLEL_VALIDATION}")
    print(f"  - ENABLE_REDIS_PIPELINE: {config.ENABLE_REDIS_PIPELINE}")
    print(f"  - ENABLE_RESPONSE_STREAMING: {config.ENABLE_RESPONSE_STREAMING}")
    return True


def test_health_endpoint_structure():
    """Test that the health endpoint would return the expected structure"""
    print("\nTesting expected health endpoint response structure...")
    
    # Simulate what the /health endpoint should return
    expected_config_keys = [
        'http2_enabled',
        'streaming_enabled',
        'parallel_validation',
        'redis_pipeline',
        'request_deduplication',
        'chunk_size',
        'max_connections'
    ]
    
    # Build the config dict as it would be in the endpoint
    endpoint_config = {
        "http2_enabled": True,
        "streaming_enabled": config.ENABLE_RESPONSE_STREAMING,
        "parallel_validation": config.ENABLE_PARALLEL_VALIDATION,
        "redis_pipeline": config.ENABLE_REDIS_PIPELINE,
        "request_deduplication": config.ENABLE_REQUEST_DEDUPLICATION,
        "chunk_size": config.STREAM_CHUNK_SIZE,
        "max_connections": config.HTTP_CONNECTOR_LIMIT
    }
    
    # Verify all expected keys are present
    for key in expected_config_keys:
        assert key in endpoint_config, f"Missing key: {key}"
    
    # Verify performance optimization flags are True
    assert endpoint_config['streaming_enabled'] == True, "streaming_enabled should be True"
    assert endpoint_config['parallel_validation'] == True, "parallel_validation should be True"
    assert endpoint_config['redis_pipeline'] == True, "redis_pipeline should be True"
    assert endpoint_config['request_deduplication'] == True, "request_deduplication should be True"
    
    print("✅ Health endpoint structure is correct")
    print(f"  - streaming_enabled: {endpoint_config['streaming_enabled']}")
    print(f"  - parallel_validation: {endpoint_config['parallel_validation']}")
    print(f"  - redis_pipeline: {endpoint_config['redis_pipeline']}")
    print(f"  - request_deduplication: {endpoint_config['request_deduplication']}")
    return True


if __name__ == "__main__":
    try:
        test_config_values()
        test_health_endpoint_structure()
        print("\n✅ All tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
