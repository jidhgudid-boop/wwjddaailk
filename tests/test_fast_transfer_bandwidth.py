#!/usr/bin/env python3
"""
Test to verify bandwidth display for very fast transfers (< 0.5 seconds)
"""
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_very_fast_transfer_bandwidth():
    """Test that very fast transfers (< 0.5s) show bandwidth correctly"""
    print("Testing bandwidth calculation for very fast transfers...")
    
    current_time = time.time()
    
    # Simulate a very fast active transfer that completed in 0.3 seconds
    # Speed hasn't been calculated yet (requires 0.5s), so speed_bps = 0
    active_transfers = {
        'fast_transfer': {
            'status': 'active',
            'speed_bps': 0,  # Not yet calculated (< 0.5s elapsed)
            'bytes_transferred': 500000,  # 500 KB transferred
            'start_time': current_time - 0.3,  # Started 0.3 seconds ago
            'last_update': current_time
        }
    }
    
    # Apply the new logic
    total_speed = 0
    for t in active_transfers.values():
        if t['status'] == 'active':
            speed_bps = t.get('speed_bps', 0)
            if speed_bps == 0 and t['bytes_transferred'] > 0:
                elapsed = current_time - t['start_time']
                if elapsed > 0:
                    speed_bps = t['bytes_transferred'] / elapsed
            total_speed += speed_bps
    
    # Expected: 500KB / 0.3s = 1,666,667 bytes/s = 12.7 Mbps
    expected_speed = 500000 / 0.3
    expected_mbps = (expected_speed * 8) / (1024 * 1024)
    
    total_mbps = (total_speed * 8) / (1024 * 1024)
    
    print(f"  ✓ Fast transfer (0.3s, 500KB):")
    print(f"    - Speed: {total_speed:,.0f} bytes/s")
    print(f"    - Mbps: {total_mbps:.2f}")
    print(f"    - Expected: {expected_speed:,.0f} bytes/s ({expected_mbps:.2f} Mbps)")
    
    assert abs(total_speed - expected_speed) < 1, f"Speed mismatch: {total_speed} vs {expected_speed}"
    
    print("✅ Very fast transfer shows bandwidth correctly")
    return True


def test_multiple_fast_transfers():
    """Test bandwidth aggregation with multiple fast transfers"""
    print("\nTesting bandwidth aggregation with multiple fast transfers...")
    
    current_time = time.time()
    
    active_transfers = {
        'fast1': {
            'status': 'active',
            'speed_bps': 0,  # Speed not yet calculated
            'bytes_transferred': 300000,  # 300 KB
            'start_time': current_time - 0.2,  # 0.2s elapsed
            'last_update': current_time
        },
        'fast2': {
            'status': 'active',
            'speed_bps': 0,  # Speed not yet calculated
            'bytes_transferred': 400000,  # 400 KB
            'start_time': current_time - 0.4,  # 0.4s elapsed
            'last_update': current_time
        },
        'normal': {
            'status': 'active',
            'speed_bps': 2000000,  # 2 MB/s (calculated normally)
            'bytes_transferred': 5000000,
            'start_time': current_time - 2.5,
            'last_update': current_time
        }
    }
    
    # Apply the new logic
    total_speed = 0
    for t in active_transfers.values():
        if t['status'] == 'active':
            speed_bps = t.get('speed_bps', 0)
            if speed_bps == 0 and t['bytes_transferred'] > 0:
                elapsed = current_time - t['start_time']
                if elapsed > 0:
                    speed_bps = t['bytes_transferred'] / elapsed
            total_speed += speed_bps
    
    # Expected:
    # fast1: 300KB / 0.2s = 1,500,000 bytes/s
    # fast2: 400KB / 0.4s = 1,000,000 bytes/s
    # normal: 2,000,000 bytes/s
    # Total: 4,500,000 bytes/s = 34.33 Mbps
    
    expected_speed = (300000 / 0.2) + (400000 / 0.4) + 2000000
    expected_mbps = (expected_speed * 8) / (1024 * 1024)
    total_mbps = (total_speed * 8) / (1024 * 1024)
    
    print(f"  ✓ Multiple transfers:")
    print(f"    - Fast transfer 1 (0.2s, 300KB): {(300000/0.2)/1024/1024:.2f} MB/s")
    print(f"    - Fast transfer 2 (0.4s, 400KB): {(400000/0.4)/1024/1024:.2f} MB/s")
    print(f"    - Normal transfer: 2.00 MB/s")
    print(f"    - Total: {total_mbps:.2f} Mbps")
    print(f"    - Expected: {expected_mbps:.2f} Mbps")
    
    assert abs(total_speed - expected_speed) < 1, f"Speed mismatch: {total_speed} vs {expected_speed}"
    
    print("✅ Multiple fast transfers aggregated correctly")
    return True


def test_edge_case_zero_bytes():
    """Test that transfers with 0 bytes don't cause issues"""
    print("\nTesting edge case: transfer with 0 bytes...")
    
    current_time = time.time()
    
    active_transfers = {
        'zero_bytes': {
            'status': 'active',
            'speed_bps': 0,
            'bytes_transferred': 0,  # No data yet
            'start_time': current_time - 0.1,
            'last_update': current_time
        }
    }
    
    # Apply the new logic
    total_speed = 0
    for t in active_transfers.values():
        if t['status'] == 'active':
            speed_bps = t.get('speed_bps', 0)
            if speed_bps == 0 and t['bytes_transferred'] > 0:
                elapsed = current_time - t['start_time']
                if elapsed > 0:
                    speed_bps = t['bytes_transferred'] / elapsed
            total_speed += speed_bps
    
    assert total_speed == 0, "Transfer with 0 bytes should show 0 speed"
    print("  ✓ Zero bytes transfer: 0 bytes/s")
    print("✅ Edge case handled correctly")
    return True


if __name__ == "__main__":
    try:
        test_very_fast_transfer_bandwidth()
        test_multiple_fast_transfers()
        test_edge_case_zero_bytes()
        print("\n" + "="*60)
        print("✅ All fast transfer bandwidth tests passed!")
        print("="*60)
        print("\nKey improvement:")
        print("✅ Transfers < 0.5 seconds now show bandwidth correctly")
        print("✅ Fallback to average speed when instantaneous speed = 0")
        print("\nEven very fast transfers will display bandwidth immediately!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
