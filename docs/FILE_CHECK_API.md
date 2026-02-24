# 文件存在性检查 API

## 概述

这些API接口用于检查视频文件是否存在，支持单个文件检查和批量检查。

## 认证

所有API端点都需要API Key认证。在请求头中可以使用以下两种格式之一：

**标准格式（推荐）：**
```
Authorization: Bearer F2UkWEJZRBxC7
```

**简化格式：**
```
Authorization: F2UkWEJZRBxC7
```

## API 端点

### 1. 检查单个文件

**端点:** `POST /api/file/check`

**请求体:**
```json
{
    "path": "/path/to/video.mp4"
}
```

**响应:**
```json
{
    "path": "/path/to/video.mp4",
    "exists": true,
    "error": null
}
```

**示例:**
```bash
curl -X POST "http://localhost:7889/api/file/check" \
  -H "Authorization: Bearer F2UkWEJZRBxC7" \
  -H "Content-Type: application/json" \
  -d '{"path": "/test/video.mp4"}'
```

### 2. 批量检查文件

**端点:** `POST /api/file/check/batch`

**请求体:**
```json
{
    "paths": [
        "/path/to/video1.mp4",
        "/path/to/video2.mp4",
        "/path/to/video3.mp4"
    ]
}
```

**响应:**
```json
{
    "results": [
        {
            "path": "/path/to/video1.mp4",
            "exists": true,
            "error": null
        },
        {
            "path": "/path/to/video2.mp4",
            "exists": false,
            "error": null
        },
        {
            "path": "/path/to/video3.mp4",
            "exists": true,
            "error": null
        }
    ],
    "total": 3,
    "exists_count": 2,
    "not_found_count": 1,
    "error_count": 0
}
```

**限制:**
- 最少: 1个文件
- 最多: 100个文件

**示例:**
```bash
curl -X POST "http://localhost:7889/api/file/check/batch" \
  -H "Authorization: Bearer F2UkWEJZRBxC7" \
  -H "Content-Type: application/json" \
  -d '{
    "paths": [
        "/test/video1.mp4",
        "/test/video2.mp4"
    ]
  }'
```

## 后端模式支持

API支持两种后端模式：

### 1. 文件系统模式 (filesystem)
- 直接检查本地文件系统中的文件
- 配置: `BACKEND_MODE = "filesystem"`
- 根目录: `BACKEND_FILESYSTEM_ROOT = "/data"`

### 2. HTTP模式 (http)
- 通过HTTP HEAD请求检查远程文件
- 配置: `BACKEND_MODE = "http"`
- 后端服务器: `BACKEND_HOST`, `BACKEND_PORT`, `BACKEND_USE_HTTPS`

## 安全特性

### 路径遍历保护
API自动检测并阻止路径遍历攻击：
- `../../etc/passwd` ❌ 被阻止
- `../../../sensitive/file` ❌ 被阻止
- `/normal/path/video.mp4` ✅ 允许

### 响应字段说明

| 字段 | 类型 | 描述 |
|------|------|------|
| `path` | string | 文件路径 |
| `exists` | boolean | 文件是否存在 |
| `error` | string\|null | 错误信息（如果有） |
| `total` | integer | 总文件数（仅批量请求） |
| `exists_count` | integer | 存在的文件数（仅批量请求） |
| `not_found_count` | integer | 未找到的文件数（仅批量请求） |
| `error_count` | integer | 检查失败的文件数（仅批量请求） |

**注意:** `exists_count + not_found_count + error_count = total`

## 错误代码

| 状态码 | 描述 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 403 | 认证失败或无权限 |
| 500 | 服务器内部错误 |

## 使用场景

1. **视频库管理**: 批量检查视频文件是否存在
2. **清理任务**: 查找缺失的文件
3. **同步验证**: 验证文件同步是否完成
4. **健康检查**: 定期检查重要文件的可用性

## 注意事项

1. API使用与现有`/api/whitelist`端点相同的认证机制
2. 批量检查最多支持100个文件路径
3. HTTP模式下使用HEAD请求以提高效率
4. 所有路径都经过安全验证，防止路径遍历攻击
