# JS白名单追踪功能（静态文件访问控制）

## 概述

JS白名单追踪功能允许你控制哪些用户（基于IP和User-Agent）可以访问特定的静态文件。虽然名称为"JS白名单"，但实际上支持所有静态文件类型，包括：
- JavaScript文件 (`.js`)
- 视频流文件 (`.m3u8`, `.ts`)
- 加密密钥文件 (`enc.key`)
- 索引文件 (`index`, `playlist`, `master`)
- 图片和字体文件 (`.jpg`, `.png`, `.woff` 等)

该功能支持两种认证方式，适合不同的使用场景。

## 核心特性

- ✅ **自动提取UA和IP**：从服务器请求中自动获取，无需在JS中传输
- ✅ **双重认证方式**：
  - API Key认证（适合后端服务器调用）
  - HMAC签名认证（适合前端调用，不暴露密钥）
- ✅ **支持多种文件类型**：
  - JavaScript (`.js`)
  - HLS视频流 (`.m3u8`, `.ts`, `enc.key`)
  - 索引文件 (`index`, `playlist`, `master`)
  - 静态资源 (`.jpg`, `.png`, `.css`, `.woff` 等)
- ✅ **智能路径匹配**：
  - 使用 `extract_match_key` 提取路径中的关键字（如 `4607b4d004_e70nxA`）
  - 同一文件夹下的所有文件共享白名单（例如：添加 `video/2025-10-27/4607b4d004_e70nxA/720p_1d1e2b/index` 后，`video/2025-10-27/4607b4d004_e70nxA/720p_1d1e2b/index.m3u8` 也可访问）
- ✅ **灵活的访问控制**：
  - **指定路径模式**：允许访问特定文件夹下的所有文件
  - **通配符模式**：路径为空时，允许访问所有静态文件
- ✅ **独立密钥配置**：使用专门的`JS_WHITELIST_SECRET_KEY`
- ✅ **签名有效期**：默认1小时（可配置）
- ✅ **支持异步加载**：defer/async模式
- ✅ **配置化管理**：可在config.py中完全开启/关闭

## 配置

在 `models/config.py` 中添加以下配置：

```python
# JS白名单追踪功能配置
ENABLE_JS_WHITELIST_TRACKER = True  # 是否启用JS白名单追踪功能
JS_WHITELIST_TRACKER_TTL = 60 * 60  # JS访问追踪记录TTL（秒），默认60分钟
JS_WHITELIST_SECRET_KEY = b"js_whitelist_secret_key_change_this"  # JS白名单HMAC签名密钥（独立配置）
JS_WHITELIST_SIGNATURE_TTL = 60 * 60  # JS白名单签名有效期（秒），默认1小时
```

⚠️ **重要**：请修改默认的 `JS_WHITELIST_SECRET_KEY` 为你自己的密钥！

## 路径匹配机制

JS白名单使用智能路径匹配，通过 `extract_match_key` 函数提取路径中的关键字：

**工作原理**:
1. 从路径中查找日期模式（YYYY-MM-DD）
2. 提取日期后的第一个文件夹作为 `match_key`
3. 使用 `match_key` 进行匹配，而不是完整路径

**示例**:
```
路径: video/2025-10-27/4607b4d004_e70nxA/720p_1d1e2b/index
提取的 match_key: 4607b4d004_e70nxA

匹配范围: 
- video/2025-10-27/4607b4d004_e70nxA/720p_1d1e2b/index ✅
- video/2025-10-27/4607b4d004_e70nxA/720p_1d1e2b/index.m3u8 ✅
- video/2025-10-27/4607b4d004_e70nxA/1080p/index.m3u8 ✅
- video/2025-10-27/OTHER_FOLDER/index.m3u8 ❌
```

**优势**: 添加一次白名单，整个文件夹下的所有文件都可访问，无需为每个文件单独添加。

## 使用方法

### 方式1：后端服务器调用（API Key认证）

适合从你的主服务器调用，需要Authorization头。

```bash
POST http://fileproxy-server:7889/api/js-whitelist
Headers:
  Authorization: ******
  Content-Type: application/json
Body:
  {
    "uid": "user123",
    "jsPath": "static/js/app.js"  # 指定路径
  }
  # 或
  {
    "uid": "user123",
    "jsPath": ""  # 通配符：允许访问所有静态文件
  }
```

**Python示例**：

```python
import requests

# 指定路径模式
response = requests.post(
    'http://fileproxy-server:7889/api/js-whitelist',
    headers={
        'Authorization': '******',
        'Content-Type': 'application/json'
    },
    json={
        'uid': 'user123',
        'jsPath': 'static/js/app.js'
    }
)

# 通配符模式（允许访问所有静态文件）
response = requests.post(
    'http://fileproxy-server:7889/api/js-whitelist',
    headers={
        'Authorization': '******',
        'Content-Type': 'application/json'
    },
    json={
        'uid': 'user123',
        'jsPath': ''  # 空路径 = 通配符
    }
)
```

### 方式2：前端调用（HMAC签名认证）

适合前端使用，不暴露API Key。签名在后端生成。

#### 步骤1：后端生成签名

```python
import hmac
import hashlib
import time

# 配置
JS_WHITELIST_SECRET_KEY = b"js_whitelist_secret_key_change_this"
JS_WHITELIST_SIGNATURE_TTL = 60 * 60  # 1小时

# 生成签名
uid = "user123"
js_path = "static/js/app.js"
expires = str(int(time.time()) + JS_WHITELIST_SIGNATURE_TTL)

message = f"{uid}:{js_path}:{expires}"
signature = hmac.new(
    JS_WHITELIST_SECRET_KEY,
    message.encode('utf-8'),
    hashlib.sha256
).hexdigest()

# 返回给前端
return {
    "uid": uid,
    "js_path": js_path,
    "expires": expires,
    "signature": signature
}
```

#### 步骤2：前端使用签名调用API

```javascript
// 1. 从你的服务器获取签名
const signResponse = await fetch('/api/generate-js-signature', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
        uid: 'user123', 
        jsPath: 'static/js/app.js' 
    })
});

const { uid, js_path, expires, signature } = await signResponse.json();

// 2. 使用签名调用FileProxy白名单API
const whitelistUrl = new URL('http://fileproxy-server:7889/api/js-whitelist');
whitelistUrl.searchParams.set('uid', uid);
whitelistUrl.searchParams.set('js_path', js_path);
whitelistUrl.searchParams.set('expires', expires);
whitelistUrl.searchParams.set('sign', signature);

// 方式1: 使用fetch (POST或GET都可以)
const response = await fetch(whitelistUrl, {
    method: 'GET'  // 或 'POST'
});

const result = await response.json();
console.log('已添加到白名单:', result);

// 方式2: 直接通过浏览器访问URL (GET)
// 用户可以直接在浏览器中访问生成的URL
window.location.href = whitelistUrl.toString();
```

**注意**: 使用HMAC签名方式时，可以选择GET或POST方法。GET方法的优势是可以直接在浏览器地址栏访问，更加简单。

#### 步骤3：在HTML中引用JS文件

```html
<!DOCTYPE html>
<html>
<head>
    <title>JS白名单示例</title>
</head>
<body>
    <!-- 使用defer异步加载（推荐） -->
    <script defer src="http://fileproxy-server:7889/static/js/app.js"></script>
    
    <!-- 使用async异步加载 -->
    <script async src="http://fileproxy-server:7889/static/js/utils.js"></script>
</body>
</html>
```

## API端点

### 1. 添加JS白名单

**POST/GET** `/api/js-whitelist`

**方式A - API Key认证（后端）** - 仅POST:
- Header: `Authorization: ******
- Body: `{"uid": "用户ID", "jsPath": "JS文件路径"}`
- 通配符模式: `{"uid": "用户ID", "jsPath": ""}` - 空路径允许访问所有静态文件

**方式B - HMAC签名认证（前端）** - GET或POST:
- Query: `?uid=用户ID&js_path=JS路径&expires=过期时间&sign=签名`
- 通配符模式: `?uid=用户ID&js_path=&expires=过期时间&sign=签名` - 空路径允许访问所有静态文件
- 签名算法: `HMAC-SHA256(JS_WHITELIST_SECRET_KEY, "uid:js_path:expires")`
- 签名格式: **十六进制字符串** (使用 `.hexdigest()`)，也支持Base64格式（向后兼容）
- 可以直接通过浏览器访问URL（GET）或通过fetch/ajax调用（POST/GET）

**访问模式说明**：
- **指定路径**: `jsPath` 为具体路径（如 `"static/js/app.js"`），只允许访问该特定文件
- **通配符模式**: `jsPath` 为空字符串（`""`），允许该IP+UA组合访问所有静态文件

**响应示例**：
```json
{
    "success": true,
    "message": "JS whitelist entry added successfully",
    "data": {
        "uid": "user123",
        "js_path": "static/js/app.js",
        "match_key": "4607b4d004_e70nxA",
        "is_wildcard": false,
        "client_ip": "192.168.1.100",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
        "ttl": 3600,
        "expires_at": 1234567890
    }
}
```

### 2. 检查白名单

**GET** `/api/js-whitelist/check?js_path=路径&uid=用户ID`

无需认证，自动使用请求的UA+IP验证。

**响应示例**：
```json
{
    "is_allowed": true,
    "js_path": "static/js/app.js",
    "uid": "user123",
    "client_ip": "192.168.1.100"
}
```

### 3. 查看统计

**GET** `/api/js-whitelist/stats?uid=用户ID`

需要API Key认证。

**响应示例**：
```json
{
    "enabled": true,
    "uid": "user123",
    "total_entries": 3,
    "ttl_config": 3600,
    "entries": [
        {
            "js_path": "static/js/app.js",
            "client_ip": "192.168.1.100",
            "user_agent": "Mozilla/5.0...",
            "created_at": 1234567890,
            "expires_at": 1234571490,
            "remaining_ttl": 3500
        }
    ]
}
```

## 工作流程

### 双重验证机制（任意一个通过即可）

FileProxy支持两种验证方式，**任意一个验证通过即可访问**：

1. **常规验证**（后端提交，**优先检查**）
   - IP白名单验证
   - 路径权限验证
   - Session验证
   
2. **JS白名单验证**（前端提交，后备验证）
   - 用户通过 `/api/js-whitelist` 添加IP+UA到白名单
   - 访问静态文件时，自动验证IP+UA是否在白名单中

**验证流程**（后端优先）:
1. **用户访问HTML页面**
2. **浏览器解析到`<script>`标签，发起JS文件请求**
3. **FileProxy服务器接收请求**
   - 自动提取User-Agent和Client-IP
4. **首先尝试后端验证（常规验证）**
   - ✅ **如果通过** → 直接返回文件内容，跳过JS白名单验证
   - ❌ **如果失败** → 继续尝试JS白名单验证（不直接拒绝）
5. **JS白名单验证**（如果后端验证失败，且是静态文件）
   - 检查IP+UA是否在JS白名单中
   - ✅ **如果通过** → 返回文件内容
   - ❌ **如果失败** → 返回403 Forbidden

**优势**: 
- 灵活的验证方式，前端提交（JS白名单）和后端提交（常规验证）任意一个有效即可，无需同时满足两者
- **后端验证优先**：避免不必要的JS白名单查询和日志，后端已批准的请求不会显示"JS白名单验证失败"消息

## 安全建议

1. ⚠️ **不要在前端代码中直接暴露API Key**
2. ✅ **前端调用时使用HMAC签名认证**
3. ✅ **修改默认的`JS_WHITELIST_SECRET_KEY`**
4. ✅ **签名由后端生成，前端仅传递签名**
5. ✅ **签名有效期为1小时，定期更新**

## defer vs async vs 普通加载

| 加载方式 | 特点 | 推荐场景 |
|---------|------|---------|
| **defer** | 异步加载，按顺序执行，不阻塞页面解析 | 需要按顺序执行的脚本 |
| **async** | 异步加载，加载完立即执行，可能乱序 | 独立的工具脚本（如统计代码） |
| **普通** | 同步加载，会阻塞页面解析 | 关键脚本，必须立即执行 |

## 示例文件

- **Python示例**: `examples/js_whitelist_example.py`
- **HTML演示**: `static/js_whitelist_demo.html`
- **测试文件**: `tests/test_js_whitelist.py`

## 运行示例

```bash
# 运行Python示例
cd Server/FileProxy
python examples/js_whitelist_example.py

# 访问HTML演示
http://localhost:7889/static/js_whitelist_demo.html
```

## 故障排查

### 问题1：签名验证失败

**原因**：
- `JS_WHITELIST_SECRET_KEY` 配置不一致
- 签名生成算法不正确
- 签名已过期（超过1小时）

**解决**：
- 确保前后端使用相同的`JS_WHITELIST_SECRET_KEY`
- 检查签名生成算法：`HMAC-SHA256(SECRET_KEY, "uid:js_path:expires")`
- 确保过期时间未超过当前时间

### 问题2：403 Forbidden

**原因**：
- UA+IP未在白名单中
- JS白名单追踪功能未启用

**解决**：
- 先调用添加白名单API
- 确保`ENABLE_JS_WHITELIST_TRACKER = True`
- 检查UA和IP是否匹配

### 问题3：功能未生效

**原因**：
- 配置未启用
- Redis连接失败

**解决**：
- 检查`ENABLE_JS_WHITELIST_TRACKER`配置
- 确保Redis服务运行正常
- 查看日志文件排查错误

## 更多信息

- **API文档**: http://localhost:7889/docs
- **监控面板**: http://localhost:7889/monitor
- **配置文件**: `models/config.py`
