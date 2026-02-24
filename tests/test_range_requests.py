#!/usr/bin/env python3
"""
Test script for HTTP Range request support
Tests resume capability (断点续传) for FileProxy
"""
import asyncio
import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.stream_proxy import StreamProxyService


def test_parse_range_header():
    """Test Range header parsing"""
    print("Testing Range header parsing...")
    
    # Create a mock service instance (without dependencies for unit test)
    class MockHTTPClient:
        pass
    
    service = StreamProxyService(MockHTTPClient())
    
    # Test cases
    test_cases = [
        # (range_header, file_size, expected_result)
        ("bytes=0-499", 1000, (0, 499)),           # Normal range
        ("bytes=500-", 1000, (500, 999)),          # Open-ended range
        ("bytes=-500", 1000, (500, 999)),          # Suffix range (last 500 bytes)
        ("bytes=0-999", 1000, (0, 999)),           # Full file
        ("bytes=0-1999", 1000, None),              # Range exceeds file size
        ("bytes=500-499", 1000, None),             # Invalid range (start > end)
        ("bytes=-2000", 1000, (0, 999)),           # Suffix larger than file
        ("invalid", 1000, None),                   # Invalid format
        ("bytes=abc-def", 1000, None),             # Non-numeric values
    ]
    
    passed = 0
    failed = 0
    
    for range_header, file_size, expected in test_cases:
        result = service._parse_range_header(range_header, file_size)
        if result == expected:
            print(f"  ✓ PASS: {range_header} (size={file_size}) -> {result}")
            passed += 1
        else:
            print(f"  ✗ FAIL: {range_header} (size={file_size})")
            print(f"    Expected: {expected}")
            print(f"    Got:      {result}")
            failed += 1
    
    print(f"\nRange header parsing tests: {passed} passed, {failed} failed\n")
    return failed == 0


def test_hls_optimization():
    """Test HLS optimization configuration"""
    print("Testing HLS optimization for 8-second TS segments (CRF 26)...")
    
    try:
        from performance_optimizer import PerformanceOptimizer
        
        # Get HLS-optimized config
        hls_config = PerformanceOptimizer.get_hls_optimized_config(
            segment_duration=8,
            crf_quality=26
        )
        
        print(f"  Optimized configuration:")
        print(f"    - Chunk Size: {hls_config['STREAM_CHUNK_SIZE']} bytes ({hls_config['STREAM_CHUNK_SIZE'] / 1024:.0f} KB)")
        print(f"    - Buffer Size: {hls_config['BUFFER_SIZE']} bytes ({hls_config['BUFFER_SIZE'] / 1024:.0f} KB)")
        print(f"    - Estimated Segment Size: {hls_config['ESTIMATED_SEGMENT_SIZE'] / (1024 * 1024):.2f} MB")
        print(f"    - Recommended Bitrate: {hls_config['RECOMMENDED_BITRATE_MBPS']:.2f} Mbps")
        
        # Verify chunk size is reasonable (should be between 16KB and 128KB)
        chunk_size = hls_config['STREAM_CHUNK_SIZE']
        if 16384 <= chunk_size <= 131072:
            print(f"  ✓ PASS: Chunk size is within optimal range (16KB - 128KB)")
            
            # Calculate transfer metrics
            estimated_size = hls_config['ESTIMATED_SEGMENT_SIZE']
            chunks_per_segment = estimated_size / chunk_size
            print(f"    - Chunks per segment: ~{chunks_per_segment:.0f}")
            print(f"    - Time to transfer at 2 Mbps: ~{(estimated_size * 8) / (2 * 1024 * 1024):.1f}s")
            
            return True
        else:
            print(f"  ✗ FAIL: Chunk size {chunk_size} is outside optimal range")
            return False
            
    except Exception as e:
        print(f"  ✗ ERROR: {str(e)}")
        return False


def main():
    """Run all tests"""
    print("=" * 70)
    print("FileProxy Range Request and HLS Optimization Tests")
    print("=" * 70)
    print()
    
    all_passed = True
    
    # Test 1: Range header parsing
    if not test_parse_range_header():
        all_passed = False
    
    # Test 2: HLS optimization
    if not test_hls_optimization():
        all_passed = False
    
    print("=" * 70)
    if all_passed:
        print("✓ All tests PASSED!")
        print("\nResume support (断点续传) is ready to use.")
        print("HLS optimization for 8-second segments (CRF 26) is configured.")
        return 0
    else:
        print("✗ Some tests FAILED!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
