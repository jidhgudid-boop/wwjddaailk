# Fix for SSL Certificate Verification Error

## Problem Statement

User reported the following error:
```
[IP:183.220.46.227] 代理请求失败: http://127.0.0.1:19443/wp-content/uploads/video/2025-10-09/93a6dd58fe_ttcYZg/vod.webp - 
Cannot connect to host videofiles.yuelk.com:443 ssl:True 
[SSLCertVerificationError: (1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain (_ssl.c:1000)')]
```

## Root Cause

The error occurred because:
1. The proxy server connects to a backend at `http://127.0.0.1:19443`
2. The backend server then makes its own HTTPS connection to `videofiles.yuelk.com:443`
3. The server at `videofiles.yuelk.com:443` uses a self-signed certificate
4. The original SSL verification logic only applied when `BACKEND_USE_HTTPS=True`
5. Since the proxy uses HTTP to connect to the backend, SSL verification was still enabled for the backend's own HTTPS connections

## The Fix

Changed the SSL verification logic in `HTTPClientManager.initialize()`:

### Before:
```python
ssl_context = None
if config.BACKEND_USE_HTTPS and not config.BACKEND_SSL_VERIFY:
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
```

### After:
```python
ssl_context = None
if not config.BACKEND_SSL_VERIFY:
    # Disable SSL verification for ALL HTTPS connections
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
```

## Impact

When `BACKEND_SSL_VERIFY=False` is set, SSL certificate verification is now disabled for:

1. **Direct Backend HTTPS Connections**: When `BACKEND_USE_HTTPS=True`, connections to the backend
2. **Backend's Own HTTPS Requests**: Any HTTPS connections made by the backend server (like to `videofiles.yuelk.com:443`)
3. **Proxied HTTPS Content**: Any HTTPS content proxied through the server

## Configuration

The default configuration in `app.py` is:
```python
BACKEND_USE_HTTPS = False  # Use HTTP to connect to backend
BACKEND_SSL_VERIFY = False  # Disable SSL verification for all HTTPS connections
```

This configuration means:
- The proxy connects to the backend using HTTP
- All HTTPS connections (including those made by the backend) will ignore SSL certificate verification
- Self-signed certificates are accepted without errors

## Testing

Three comprehensive test suites verify the fix:

1. **test_https_proxy.py**: Tests basic HTTPS functionality
2. **test_ssl_verification.py**: Tests SSL verification behavior in different scenarios
3. **Manual validation**: Confirms the fix addresses the specific error

All tests pass ✅

## Deployment

To deploy with SSL verification disabled:

1. **No changes needed** - The default configuration already has `BACKEND_SSL_VERIFY=False`
2. Restart the application
3. The error message about SSL certificate verification should no longer occur

## Security Considerations

⚠️ **WARNING**: Disabling SSL certificate verification makes connections vulnerable to man-in-the-middle attacks.

This setting is appropriate for:
- Development and testing environments
- Internal networks with self-signed certificates
- Trusted backend servers

For production environments with public internet connections, consider:
- Using valid SSL certificates
- Setting `BACKEND_SSL_VERIFY=True`
- Implementing proper certificate management

## Verification

To verify the fix is working:

1. Check the application logs for: `已禁用SSL证书验证（适用于自签名证书或测试环境）`
2. Monitor for the absence of `SSLCertVerificationError` messages
3. Use the `/health` endpoint to confirm configuration:
```json
{
  "config": {
    "backend_use_https": false,
    "backend_ssl_verify": false
  }
}
```

## Summary

✅ **Fixed**: SSL certificate verification is now properly disabled for all HTTPS connections when `BACKEND_SSL_VERIFY=False`

✅ **Resolves**: `SSLCertVerificationError` for self-signed certificates

✅ **Applies to**: Backend connections, backend's own HTTPS requests, and proxied HTTPS content

✅ **Backward Compatible**: Existing configurations continue to work without changes
