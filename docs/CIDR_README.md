# CIDR Support for File Proxy Server

The file proxy server now supports CIDR (Classless Inter-Domain Routing) notation for flexible IP matching, allowing you to specify IP ranges instead of just exact IP addresses.

## Features

### Supported Formats
- **Exact IP**: `192.168.1.100` (backward compatible)
- **CIDR notation**: `192.168.1.0/24` (matches 192.168.1.1 - 192.168.1.254)
- **Single IP as CIDR**: `192.168.1.100/32` (equivalent to exact match)

### Common CIDR Examples
- `192.168.1.0/24` - Matches 192.168.1.1 to 192.168.1.254 (256 addresses)
- `10.0.0.0/8` - Matches 10.0.0.1 to 10.255.255.254 (16M addresses)
- `172.16.0.0/12` - Matches 172.16.0.1 to 172.31.255.254 (1M addresses)
- `127.0.0.0/8` - Localhost range

## API Usage

### Add IP Whitelist with CIDR Support

**Endpoint**: `POST /api/whitelist`

**Headers**:
```
Authorization: Bearer F2UkWEJZRBxC7
Content-Type: application/json
```

#### New Format (Recommended)
```json
{
  "uid": "user123",
  "path": "/path/to/resource/2024-01-15/video123",
  "UserAgent": "Mozilla/5.0...",
  "ipPatterns": [
    "192.168.1.0/24",
    "10.0.0.50/32",
    "172.16.0.0/12"
  ]
}
```

#### Backward Compatible Format
```json
{
  "uid": "user123",
  "path": "/path/to/resource/2024-01-15/video123",
  "UserAgent": "Mozilla/5.0...",
  "clientIp": "192.168.1.100"
}
```

### Response Example
```json
{
  "message": "IP whitelist added successfully with CIDR support",
  "key_path": "video123",
  "ip_patterns": ["192.168.1.0/24", "10.0.0.50/32"],
  "cidr_examples": {
    "192.168.1.0/24": ["192.168.1.1", "192.168.1.2", "192.168.1.3"]
  },
  "ua_hash": "a1b2c3d4",
  "ttl": 3600,
  "operations_completed": "3/3",
  "worker_pid": 12345
}
```

## Debug Endpoints

### Test CIDR Matching
**GET** `/debug/cidr?ip=192.168.1.100&cidr=192.168.1.0/24`

```json
{
  "test_ip": "192.168.1.100",
  "test_cidr": "192.168.1.0/24",
  "is_valid_ip": true,
  "is_valid_cidr": true,
  "ip_in_cidr": true,
  "normalized_cidr": "192.168.1.0/24",
  "cidr_examples": ["192.168.1.1", "192.168.1.2", "192.168.1.3", "192.168.1.4", "192.168.1.5"],
  "pattern_tests": {
    "192.168.1.100": {"is_cidr": false, "matches": true},
    "192.168.1.0/24": {"is_cidr": true, "matches": true}
  }
}
```

### Debug IP Whitelist
**GET** `/debug/ip-whitelist?ip=192.168.1.100&path=/test/2024-01-15/video123`

Shows current whitelist entries and matching results.

## Implementation Benefits

1. **Flexible Network Management**: Allow entire subnets instead of individual IPs
2. **Reduced Configuration**: One CIDR entry covers multiple IPs
3. **Dynamic Networks**: Support for DHCP environments where IPs change
4. **Backward Compatibility**: Existing exact IP configurations continue to work
5. **Security**: Granular control over network access ranges

## Migration Guide

### For Existing Users
No action required - existing exact IP configurations continue to work unchanged.

### For New Setups
Use the new `ipPatterns` array parameter to specify CIDR ranges:

```bash
# Allow entire office network
curl -X POST "https://your-server.com/api/whitelist" \
  -H "Authorization: Bearer F2UkWEJZRBxC7" \
  -H "Content-Type: application/json" \
  -d '{
    "uid": "user123",
    "path": "/media/2024-01-15/video123",
    "UserAgent": "Mozilla/5.0 (compatible; MyApp/1.0)",
    "ipPatterns": ["192.168.1.0/24"]
  }'
```

## Technical Notes

- Uses Python's built-in `ipaddress` module for reliable IP/CIDR handling
- Supports both IPv4 and IPv6 (IPv6 uses /128 for single addresses)
- Redis storage optimized for both exact matching and pattern-based lookup
- Automatic normalization of IP inputs (e.g., `192.168.1.100` → `192.168.1.100/32`)
- Efficient matching algorithm that tries exact matches first, then CIDR patterns