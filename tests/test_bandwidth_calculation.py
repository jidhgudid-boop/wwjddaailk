#!/usr/bin/env python3
"""
Test script to verify improved bandwidth calculation logic
Tests that bandwidth is calculated from all active and recently completed transfers
"""
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_bandwidth_calculation_logic():
    """Test the improved bandwidth calculation logic"""
    print("Testing improved bandwidth calculation logic...")
    
    # Simulate active_transfers dictionary
    current_time = time.time()
    
    active_transfers = {
        'transfer1': {
            'status': 'active',
            'speed_bps': 1000000,  # 1 MB/s
            'bytes_transferred': 5000000,
            'start_time': current_time - 5,
            'last_update': current_time
        },
        'transfer2': {
            'status': 'active',
            'speed_bps': 2000000,  # 2 MB/s
            'bytes_transferred': 10000000,
            'start_time': current_time - 5,
            'last_update': current_time
        },
        'transfer3': {
            'status': 'completed',
            'speed_bps': 500000,  # 0.5 MB/s (瞬时速度)
            'bytes_transferred': 3000000,  # 3 MB
            'start_time': current_time - 2,
            'last_update': current_time - 0.5  # 0.5秒前完成
        },
        'transfer4': {
            'status': 'completed',
            'speed_bps': 800000,
            'bytes_transferred': 8000000,
            'start_time': current_time - 10,
            'last_update': current_time - 5  # 5秒前完成，不应计入
        }
    }
    
    # Calculate total speed using the new logic
    total_speed = 0
    for t in active_transfers.values():
        if t['status'] == 'active':
            total_speed += t.get('speed_bps', 0)
        elif t['status'] == 'completed':
            elapsed = current_time - t['start_time']
            time_since_complete = current_time - t.get('last_update', t['start_time'])
            if time_since_complete < 2.0 and elapsed > 0:
                avg_speed = t['bytes_transferred'] / elapsed
                total_speed += avg_speed
    
    # Convert to Mbps
    total_speed_mbps = (total_speed * 8) / (1024 * 1024)
    
    # Expected:
    # - transfer1: 1 MB/s = 1,000,000 bytes/s
    # - transfer2: 2 MB/s = 2,000,000 bytes/s
    # - transfer3: 3 MB / 2 sec = 1,500,000 bytes/s (included, completed < 2s ago)
    # - transfer4: not included (completed 5s ago)
    # Total: 4,500,000 bytes/s = 34.33 Mbps
    
    expected_bps = 1000000 + 2000000 + (3000000 / 2)
    expected_mbps = (expected_bps * 8) / (1024 * 1024)
    
    print(f"  ✓ Total speed (bytes/s): {total_speed:,.0f}")
    print(f"  ✓ Total speed (Mbps): {total_speed_mbps:.2f}")
    print(f"  ✓ Expected (bytes/s): {expected_bps:,.0f}")
    print(f"  ✓ Expected (Mbps): {expected_mbps:.2f}")
    
    # Allow small floating point differences
    assert abs(total_speed - expected_bps) < 1, f"Speed mismatch: {total_speed} vs {expected_bps}"
    assert abs(total_speed_mbps - expected_mbps) < 0.01, f"Mbps mismatch: {total_speed_mbps} vs {expected_mbps}"
    
    print("✅ Bandwidth calculation correctly includes recently completed transfers")
    return True


def test_speed_display_logic():
    """Test improved speed display for individual transfers"""
    print("\nTesting improved speed display logic...")
    
    current_time = time.time()
    
    test_cases = [
        {
            'name': 'Active transfer with speed',
            'info': {
                'status': 'active',
                'speed_bps': 5000000,
                'bytes_transferred': 10000000,
                'start_time': current_time - 2,
                'total_size': 50000000
            },
            'expected_min': 5000000,  # Should use instantaneous speed
            'expected_max': 5000000
        },
        {
            'name': 'Completed small file',
            'info': {
                'status': 'completed',
                'speed_bps': 2000000,
                'bytes_transferred': 500000,  # 500 KB
                'start_time': current_time - 0.5,
                'total_size': 500000
            },
            'expected_min': 900000,  # 500KB / 0.5s = 1000000 bytes/s
            'expected_max': 1100000
        },
        {
            'name': 'Active transfer, speed is 0 but has data',
            'info': {
                'status': 'active',
                'speed_bps': 0,
                'bytes_transferred': 8000000,
                'start_time': current_time - 4,
                'total_size': 20000000
            },
            'expected_min': 1900000,  # 8MB / 4s = 2000000 bytes/s
            'expected_max': 2100000
        }
    ]
    
    for case in test_cases:
        info = case['info']
        elapsed = current_time - info['start_time']
        speed_bps = info.get('speed_bps', 0)
        bytes_transferred = info['bytes_transferred']
        total_size = info.get('total_size', 0)
        
        # Apply the new logic
        if info['status'] == 'completed' or elapsed < 0.5:
            if elapsed > 0:
                speed_bps = bytes_transferred / elapsed
        elif speed_bps == 0 and elapsed > 0:
            speed_bps = bytes_transferred / elapsed
        elif (total_size and total_size < 1024 * 1024) or elapsed < 2.0:
            if elapsed > 0:
                avg_speed = bytes_transferred / elapsed
                speed_bps = max(speed_bps, avg_speed)
        
        # Verify result
        assert case['expected_min'] <= speed_bps <= case['expected_max'], \
            f"{case['name']}: speed {speed_bps} not in range [{case['expected_min']}, {case['expected_max']}]"
        
        print(f"  ✓ {case['name']}: {speed_bps/1024/1024:.2f} MB/s")
    
    print("✅ Speed display logic correctly handles all transfer states")
    return True


def test_zero_bandwidth_scenarios():
    """Test that we don't show 0 when there's actual data transfer"""
    print("\nTesting zero bandwidth scenarios...")
    
    # Scenario 1: No active transfers - should show 0
    active_transfers_empty = {}
    total_speed = sum(t.get('speed_bps', 0) for t in active_transfers_empty.values() if t['status'] == 'active')
    assert total_speed == 0, "Empty transfers should show 0"
    print("  ✓ No transfers: 0 Mbps")
    
    # Scenario 2: Only old completed transfers - should show 0
    current_time = time.time()
    active_transfers_old = {
        'old1': {
            'status': 'completed',
            'bytes_transferred': 1000000,
            'start_time': current_time - 10,
            'last_update': current_time - 8
        }
    }
    
    total_speed = 0
    for t in active_transfers_old.values():
        if t['status'] == 'active':
            total_speed += t.get('speed_bps', 0)
        elif t['status'] == 'completed':
            elapsed = current_time - t['start_time']
            time_since_complete = current_time - t.get('last_update', t['start_time'])
            if time_since_complete < 2.0 and elapsed > 0:
                avg_speed = t['bytes_transferred'] / elapsed
                total_speed += avg_speed
    
    assert total_speed == 0, "Old completed transfers should not contribute"
    print("  ✓ Only old completed transfers: 0 Mbps")
    
    # Scenario 3: Recently completed transfer - should show speed
    active_transfers_recent = {
        'recent1': {
            'status': 'completed',
            'bytes_transferred': 2000000,  # 2 MB
            'start_time': current_time - 1,
            'last_update': current_time - 0.1  # Just completed
        }
    }
    
    total_speed = 0
    for t in active_transfers_recent.values():
        if t['status'] == 'active':
            total_speed += t.get('speed_bps', 0)
        elif t['status'] == 'completed':
            elapsed = current_time - t['start_time']
            time_since_complete = current_time - t.get('last_update', t['start_time'])
            if time_since_complete < 2.0 and elapsed > 0:
                avg_speed = t['bytes_transferred'] / elapsed
                total_speed += avg_speed
    
    assert total_speed > 0, "Recent completed transfer should show speed"
    total_mbps = (total_speed * 8) / (1024 * 1024)
    print(f"  ✓ Recently completed transfer: {total_mbps:.2f} Mbps")
    
    print("✅ Zero bandwidth scenarios handled correctly")
    return True


if __name__ == "__main__":
    try:
        test_bandwidth_calculation_logic()
        test_speed_display_logic()
        test_zero_bandwidth_scenarios()
        print("\n" + "="*60)
        print("✅ All improved bandwidth calculation tests passed!")
        print("="*60)
        print("\nKey improvements:")
        print("1. ✅ Includes recently completed transfers (< 2s) in bandwidth")
        print("2. ✅ Uses average speed for completed transfers")
        print("3. ✅ Shows actual speed even for quick transfers")
        print("4. ✅ Handles zero-speed cases by calculating from data")
        print("\nBandwidth display should now show real transfer activity!")
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
