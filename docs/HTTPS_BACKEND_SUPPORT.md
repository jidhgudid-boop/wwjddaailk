# HTTPS Backend Proxy Support

## Overview

This proxy server now supports connecting to backend servers via HTTPS with optional SSL certificate verification control.

## Configuration

Two new configuration options have been added to the `OptimizedConfig` class:

### BACKEND_USE_HTTPS
- **Type**: `bool`
- **Default**: `False`
- **Description**: Enable HTTPS for backend connections
- **Usage**: Set to `True` to use HTTPS instead of HTTP when connecting to the backend server

### BACKEND_SSL_VERIFY
- **Type**: `bool`
- **Default**: `False`
- **Description**: Control SSL certificate verification for ALL HTTPS connections
- **Important**: This setting applies to:
  1. Direct HTTPS connections to the backend (when `BACKEND_USE_HTTPS=True`)
  2. Any HTTPS connections made by the backend server itself
  3. Any other HTTPS requests proxied through this server
- **Usage**: 
  - Set to `False` to disable SSL certificate verification (useful for self-signed certificates or testing environments)
  - Set to `True` to enable full SSL certificate verification (recommended for production with valid certificates)

## Implementation Details

### SSL Context Creation

When `BACKEND_USE_HTTPS` is `True` and `BACKEND_SSL_VERIFY` is `False`, the proxy creates an SSL context with disabled certificate verification:

```python
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
```

This SSL context is then passed to the `TCPConnector` during HTTP client initialization.

### URL Construction

The backend URL is constructed dynamically based on the `BACKEND_USE_HTTPS` setting:

```python
backend_scheme = "https" if config.BACKEND_USE_HTTPS else "http"
remote_url = f"{backend_scheme}://{config.BACKEND_HOST}:{config.BACKEND_PORT}/{path}"
```

## Usage Examples

### Example 1: HTTP Backend (Default)

```python
# In app.py or configuration
BACKEND_USE_HTTPS = False
BACKEND_SSL_VERIFY = False  # Ignored when HTTPS is disabled
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 27804

# Results in URLs like: http://127.0.0.1:27804/path/to/file.m3u8
```

### Example 2: HTTPS Backend with Self-Signed Certificate

```python
# In app.py or configuration
BACKEND_USE_HTTPS = True
BACKEND_SSL_VERIFY = False  # Disable verification for self-signed certs
BACKEND_HOST = "backend.example.com"
BACKEND_PORT = 443

# Results in URLs like: https://backend.example.com:443/path/to/file.m3u8
# SSL certificate verification is disabled
```

### Example 3: HTTPS Backend with Valid Certificate

```python
# In app.py or configuration
BACKEND_USE_HTTPS = True
BACKEND_SSL_VERIFY = True  # Enable verification for valid certs
BACKEND_HOST = "backend.example.com"
BACKEND_PORT = 443

# Results in URLs like: https://backend.example.com:443/path/to/file.m3u8
# SSL certificate verification is enabled
```

## Security Considerations

### When to Disable SSL Verification (BACKEND_SSL_VERIFY = False)

- **Development/Testing**: When using self-signed certificates in development environments
- **Internal Networks**: When backend servers use self-signed certificates that are trusted within the network
- **Legacy Systems**: When working with legacy systems that have certificate issues

### When to Enable SSL Verification (BACKEND_SSL_VERIFY = True)

- **Production**: Always use valid SSL certificates and enable verification in production
- **Public Internet**: When connecting to backend servers over the public internet
- **Compliance**: When security compliance requires full certificate validation

### Security Warning

⚠️ **WARNING**: Disabling SSL certificate verification (`BACKEND_SSL_VERIFY = False`) makes the connection vulnerable to man-in-the-middle attacks. Only use this setting in trusted environments or for development/testing purposes.

## Testing

Run the test suite to verify HTTPS functionality:

```bash
cd /home/runner/work/YuemPyScripts/YuemPyScripts/Server/FileProxy
python3 test_https_proxy.py
```

## Health Check

The `/health` endpoint now reports HTTPS configuration status:

```bash
curl http://localhost:7888/health
```

Response includes:
```json
{
  "config": {
    "backend_use_https": false,
    "backend_ssl_verify": false,
    ...
  }
}
```

## Affected Components

### HTTPClientManager
- Modified to create SSL context when HTTPS is enabled with verification disabled
- SSL context is passed to `TCPConnector` during initialization

### proxy_handler
- Updated to construct URLs using the configured scheme (HTTP/HTTPS)

### probe_backend_file
- Updated to use the same URL construction logic as proxy_handler

### health_check
- Updated to report HTTPS and SSL verification status

## Backward Compatibility

All changes are backward compatible:
- Default configuration uses HTTP (no SSL)
- Existing HTTP-based deployments continue to work without any changes
- HTTPS support is opt-in via configuration

## Changelog

### Version with HTTPS Support
- Added `BACKEND_USE_HTTPS` configuration option
- Added `BACKEND_SSL_VERIFY` configuration option
- Modified `HTTPClientManager` to support SSL context configuration
- Updated URL construction to support both HTTP and HTTPS
- Added comprehensive test suite for HTTPS functionality
- Updated health check endpoint to report HTTPS status
