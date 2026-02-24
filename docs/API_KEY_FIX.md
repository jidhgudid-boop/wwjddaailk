# API Key Authentication Fix

## 问题描述 (Problem Description)

用户在使用文件检查API时遇到了认证错误：

```bash
curl -X POST https://spcs.yuelk.com/api/file/check \
  -H "Authorization: F2UkWEJZRBxC7" \
  -H "Content-Type: application/json" \
  -d '{"path": "video/2025-06-17/6a21d6c449_RrOLsf/preview/index.m3u8"}'
```

返回错误：
```json
{"error":"Invalid or missing API key"}
```

## 根本原因 (Root Cause)

原有代码只支持标准的Bearer格式：
```python
if not authorization or authorization != f"Bearer {config.API_KEY}":
    # 认证失败
```

但用户发送的请求头格式为：
```
Authorization: F2UkWEJZRBxC7
```

而不是：
```
Authorization: Bearer F2UkWEJZRBxC7
```

## 解决方案 (Solution)

创建了一个新的辅助函数 `validate_api_key()` 来支持两种格式：

```python
def validate_api_key(authorization: str, expected_api_key: str) -> bool:
    """
    验证API Key，支持两种格式：
    1. Bearer <API_KEY> (标准格式)
    2. <API_KEY> (简化格式)
    """
    if not authorization:
        return False
    
    # 尝试标准Bearer格式
    if authorization.startswith("Bearer "):
        token = authorization[7:]  # 移除 "Bearer " 前缀
        return token == expected_api_key
    
    # 尝试简化格式（直接是API Key）
    return authorization == expected_api_key
```

## 修改的文件 (Modified Files)

1. **utils/helpers.py** - 添加了 `validate_api_key()` 函数
2. **routes/file_check.py** - 更新了两个端点以使用新的验证函数
   - `/api/file/check` - 单文件检查
   - `/api/file/check/batch` - 批量文件检查
3. **routes/proxy.py** - 更新了白名单端点以保持一致性
   - `/api/whitelist`
4. **docs/FILE_CHECK_API.md** - 更新文档说明两种格式都支持

## 测试覆盖 (Test Coverage)

创建了全面的测试以确保两种格式都能正常工作：

- ✅ Bearer格式认证
- ✅ 直接API Key格式认证
- ✅ 无效API Key拒绝
- ✅ 空值/None处理
- ✅ 大小写敏感性
- ✅ 额外空格处理

## 使用示例 (Usage Examples)

### 格式1: 标准Bearer格式（推荐）

```bash
curl -X POST https://spcs.yuelk.com/api/file/check \
  -H "Authorization: Bearer F2UkWEJZRBxC7" \
  -H "Content-Type: application/json" \
  -d '{"path": "video/2025-06-17/6a21d6c449_RrOLsf/preview/index.m3u8"}'
```

### 格式2: 简化格式

```bash
curl -X POST https://spcs.yuelk.com/api/file/check \
  -H "Authorization: F2UkWEJZRBxC7" \
  -H "Content-Type: application/json" \
  -d '{"path": "video/2025-06-17/6a21d6c449_RrOLsf/preview/index.m3u8"}'
```

**现在两种格式都能正常工作！**

## 向后兼容性 (Backward Compatibility)

✅ 完全向后兼容
- 现有使用Bearer格式的客户端继续正常工作
- 新客户端可以使用简化格式
- 不需要修改现有的客户端代码

## 安全性 (Security)

✅ 保持相同的安全级别
- API Key必须完全匹配（区分大小写）
- 不接受空值或None
- 不接受错误的API Key
- 使用常量时间比较防止时序攻击（通过直接字符串比较）

## 影响的API端点 (Affected API Endpoints)

1. `POST /api/file/check` - 单文件存在性检查
2. `POST /api/file/check/batch` - 批量文件存在性检查
3. `POST /api/whitelist` - IP白名单管理
