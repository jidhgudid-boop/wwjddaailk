# 多UA+IP对和静态文件验证功能文档

## 概述

本文档描述FileProxy服务器的两个新功能：
1. **多UA+IP对管理** - 允许单个UID下添加多个User-Agent + IP组合
2. **静态文件IP-only验证** - 对静态文件（如webp、jpg等）只验证IP+UA，跳过路径检查

## 1. 多UA+IP对管理

### 功能说明

在原有系统中，每个UA+IP组合独立存储。新功能在UID级别追踪所有UA+IP对，实现：
- 单个UID可以有多个不同的UA+IP组合（例如：手机浏览器、桌面浏览器、不同网络IP）
- 自动FIFO（先进先出）替换机制，当超过最大数量时自动删除最旧的UA+IP对
- 无需修改API，向后兼容

### 配置参数

在 `models/config.py` 中：

```python
# UID下允许的最大UA+IP组合数
MAX_UA_IP_PAIRS_PER_UID = 5  # 默认值：5
```

### 工作原理

#### 数据结构

1. **IP+UA访问键** (保持不变)
   ```
   Redis键: ip_cidr_access:{ip_pattern}:{ua_hash}
   内容: {
       "uid": "user123",
       "key_path": "video/abc123",
       "paths": [...],
       "ip_patterns": ["192.168.1.0/24"],
       "user_agent": "Mozilla/5.0...",
       "created_at": 1234567890
   }
   ```

2. **UID级UA+IP对追踪** (新增)
   ```
   Redis键: uid_ua_ip_pairs:{uid}
   内容: [
       {
           "pair_id": "192.168.1.0/24:abc12345",
           "ip_pattern": "192.168.1.0/24",
           "ua_hash": "abc12345",
           "created_at": 1234567890,
           "last_updated": 1234567890
       },
       ...
   ]
   ```

#### FIFO替换流程

1. 当添加新的UA+IP对时，检查当前UID的总对数
2. 如果未超过 `MAX_UA_IP_PAIRS_PER_UID`，直接添加
3. 如果超过限制：
   - 按 `created_at` 排序所有对
   - 移除最旧的对
   - 删除对应的 `ip_cidr_access` Redis键
   - 添加新的对

### 使用示例

#### API调用（无需修改）

```bash
# 添加第一个UA+IP对
curl -X POST http://localhost:7889/api/whitelist \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "uid": "user123",
    "path": "/video/abc123/playlist.m3u8",
    "clientIp": "192.168.1.100",
    "UserAgent": "Mozilla/5.0 (Windows NT 10.0) Chrome/120.0"
  }'

# 添加第二个UA+IP对（相同UID，不同IP或UA）
curl -X POST http://localhost:7889/api/whitelist \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "uid": "user123",
    "path": "/video/abc123/playlist.m3u8",
    "clientIp": "10.0.0.50",
    "UserAgent": "Mozilla/5.0 (iPhone; iOS 17.0) Safari/17.0"
  }'
```

#### 响应示例

```json
{
  "success": true,
  "message": "CIDR whitelist added/updated successfully",
  "key_path": "video/abc123",
  "ip_pattern": "192.168.1.0/24",
  "ua_hash": "abc12345",
  "ttl": 3600,
  "uid_ua_ip_pairs_info": {
    "max_pairs_per_uid": 5,
    "current_pairs_count": 2,
    "pairs_removed": 0,
    "pair_replacement_policy": "FIFO (oldest UA+IP pairs are removed when limit exceeded)"
  }
}
```

## 2. 静态文件IP-only验证

### 功能说明

对于静态资源文件（如图片、CSS、字体等），开启此功能后：
- 只验证IP+UA组合是否在白名单中
- **跳过路径（key_path）匹配检查**
- 允许访问任意路径下的静态文件

这对于使用CDN或静态资源服务器的场景特别有用。

### 配置参数

在 `models/config.py` 中：

```python
# 是否对静态文件仅验证IP（跳过路径保护）
ENABLE_STATIC_FILE_IP_ONLY_CHECK = False  # 默认：关闭

# 静态文件扩展名列表
STATIC_FILE_EXTENSIONS = (
    '.webp', '.jpg', '.jpeg', '.png', '.gif', '.svg',  # 图片
    '.css', '.js',  # 样式和脚本
    '.woff', '.woff2', '.ttf', '.eot',  # 字体
    '.ico', '.txt'  # 其他静态资源
)
```

### 工作原理

#### 验证流程

```python
# 在 routes/proxy.py 中
1. 检查是否为静态文件（通过扩展名）
2. 如果 ENABLE_STATIC_FILE_IP_ONLY_CHECK=True:
   - 静态文件不跳过验证，进入验证流程
   - 在 check_ip_key_path() 中只验证 IP+UA，跳过路径检查
3. 如果 ENABLE_STATIC_FILE_IP_ONLY_CHECK=False (默认):
   - 静态文件完全跳过验证，任何人可访问

# 在 services/auth_service.py 的 check_ip_key_path() 函数中
1. 检查文件扩展名是否在 STATIC_FILE_EXTENSIONS 中
2. 如果是静态文件且 ENABLE_STATIC_FILE_IP_ONLY_CHECK=True:
   a. 只验证 IP+UA 是否在白名单中
   b. 跳过 key_path 路径匹配
   c. 返回允许访问
3. 否则，执行正常的路径验证流程
```

**重要说明**：
- 当 `ENABLE_STATIC_FILE_IP_ONLY_CHECK=True` 时，静态文件**需要IP在白名单中**才能访问
- 当 `ENABLE_STATIC_FILE_IP_ONLY_CHECK=False` 时，静态文件**完全开放访问**，无需认证

#### 示例场景

**场景1：关闭IP-only验证（默认，ENABLE_STATIC_FILE_IP_ONLY_CHECK=False）**
```
用户被授权访问: /video/abc123/*
静态文件行为: 完全开放访问，无需认证

请求1: /video/abc123/logo.webp    ✅ 允许（静态文件，开放访问）
请求2: /static/images/logo.webp   ✅ 允许（静态文件，开放访问）
请求3: /video/abc123/playlist.m3u8 ✅ 允许（路径匹配+认证）
请求4: /other/video/file.m3u8     ❌ 拒绝（路径不匹配）
```

**场景2：开启IP-only验证（ENABLE_STATIC_FILE_IP_ONLY_CHECK=True）**
```
用户被授权访问: /video/abc123/*
静态文件行为: 需要IP+UA在白名单，但不需要路径匹配

请求1: /video/abc123/logo.webp    ✅ 允许（静态文件+IP验证通过）
请求2: /static/images/logo.webp   ✅ 允许（静态文件+IP验证通过）
请求3: /video/abc123/playlist.m3u8 ✅ 允许（路径匹配+认证）
请求4: /other/video/file.m3u8     ❌ 拒绝（非静态，路径不匹配）

注意：如果IP不在白名单中，所有静态文件请求都会被拒绝
```

### 使用建议

#### 何时启用

- ✅ 使用CDN分发静态资源
- ✅ 静态文件散布在多个路径下
- ✅ 需要灵活访问静态资源
- ✅ 安全风险较低（静态资源）

#### 何时禁用

- ❌ 需要严格的路径权限控制
- ❌ 敏感的静态资源（如私有图片）
- ❌ 不希望用户访问任意路径的静态文件

### 安全注意事项

1. **仅适用于真正的静态资源**：不要将需要权限控制的文件扩展名添加到 `STATIC_FILE_EXTENSIONS`
2. **IP+UA验证仍然有效**：只有白名单中的IP+UA组合才能访问
3. **非静态文件不受影响**：m3u8、ts、key等流媒体文件仍然需要路径验证

## 测试

### 单元测试

运行单元测试（不需要Redis）：
```bash
cd Server/FileProxy
python tests/test_ua_ip_pairs_unit.py
```

### 集成测试

运行集成测试（需要Redis连接）：
```bash
cd Server/FileProxy
python tests/test_multiple_ua_ip_pairs.py
```

## 向后兼容性

- ✅ API接口完全兼容，无需修改客户端代码
- ✅ 现有的单UA+IP配置继续工作
- ✅ 默认配置保持现有行为（静态文件IP-only验证默认关闭）
- ✅ 逐步迁移：可以混合使用新旧方式

## 监控和调试

### 查看UID的UA+IP对

```python
import redis
r = redis.Redis(host='localhost', port=6379, db=6)
uid_pairs = r.get('uid_ua_ip_pairs:user123')
print(uid_pairs)
```

### 日志信息

系统会记录以下关键信息：
- 添加新UA+IP对时的日志
- FIFO替换时的日志（包括被删除的对）
- 静态文件IP-only验证的日志

查看日志：
```bash
tail -f logs/proxy_fastapi.log | grep -E "UID UA+IP对|静态文件IP"
```

## 常见问题

### Q1: 为什么我的旧UA+IP对被删除了？

A: 当单个UID下的UA+IP对数量超过 `MAX_UA_IP_PAIRS_PER_UID` 时，系统会自动删除最旧的对。建议：
- 增加 `MAX_UA_IP_PAIRS_PER_UID` 的值
- 定期清理不再使用的UID

### Q2: 如何临时禁用FIFO替换？

A: 设置一个很大的 `MAX_UA_IP_PAIRS_PER_UID` 值（如100），但这会增加Redis内存使用。

### Q3: 静态文件IP-only验证会影响性能吗？

A: 不会。实际上可能会略微提升性能，因为跳过了路径匹配检查。

### Q4: 可以为不同的UID设置不同的最大对数吗？

A: 当前版本不支持，所有UID使用相同的 `MAX_UA_IP_PAIRS_PER_UID` 配置。如需此功能，可以在未来版本中添加。

## 3. 静态文件专用白名单API

### 功能说明

新增专用于静态文件访问的白名单API，无需提供路径信息。

**特点：**
- 无需提供 `path` 参数，只需 `uid` + `clientIp` + `UserAgent`
- 独立Redis键存储（`static_file_access:`前缀）
- 与路径白名单互不干扰，可同时使用
- 支持多个UA+IP组合，同样有FIFO替换机制
- TTL与路径白名单相同

### API端点

**POST /api/static-whitelist**

添加UA+IP到静态文件白名单（无需路径）

#### 请求参数

```json
{
  "uid": "user123",
  "clientIp": "192.168.1.100",
  "UserAgent": "Mozilla/5.0 (Windows NT 10.0) Chrome/120.0"
}
```

**注意：** 无需提供 `path` 参数

#### 请求示例

```bash
curl -X POST http://localhost:7889/api/static-whitelist \
  -H "Authorization: ******" \
  -H "Content-Type: application/json" \
  -d '{
    "uid": "user123",
    "clientIp": "192.168.1.100",
    "UserAgent": "Mozilla/5.0 (Windows NT 10.0) Chrome/120.0"
  }'
```

#### 响应示例

```json
{
  "success": true,
  "message": "Static file whitelist added/updated successfully",
  "ip_pattern": "192.168.1.0/24",
  "ua_hash": "abc12345",
  "ttl": 3600,
  "uid_static_ua_ip_pairs_info": {
    "max_pairs_per_uid": 5,
    "current_pairs_count": 1,
    "pairs_removed": 0,
    "pair_replacement_policy": "FIFO (oldest UA+IP pairs are removed when limit exceeded)"
  }
}
```

### 数据结构

#### Redis键格式

```
static_file_access:{ip_pattern}:{ua_hash}
uid_static_ua_ip_pairs:{uid}
```

示例：
```
static_file_access:192.168.1.0_24:abc12345
uid_static_ua_ip_pairs:user123
```

#### 数据内容

```json
{
  "uid": "user123",
  "ip_patterns": ["192.168.1.0/24"],
  "user_agent": "Mozilla/5.0...",
  "created_at": 1234567890,
  "access_type": "static_files_only"
}
```

### 访问流程

当静态文件请求到达时：

1. 检测文件扩展名是否为静态文件
2. 如果 `ENABLE_STATIC_FILE_IP_ONLY_CHECK=True`：
   - **首先**检查 `static_file_access` 独立白名单
   - 如果匹配，立即允许访问（无需路径验证）
   - 如果不匹配，继续检查路径白名单 `ip_cidr_access`
3. 验证IP+UA组合
4. 允许或拒绝访问

### 使用场景

#### 场景1：只访问静态资源

```bash
# 用户只需要访问静态文件（图片、CSS、JS等）
POST /api/static-whitelist
{
  "uid": "user123",
  "clientIp": "192.168.1.100",
  "UserAgent": "Mozilla/5.0..."
}

# 结果：可以访问所有静态文件
✅ /static/logo.webp
✅ /images/photo.jpg
✅ /css/style.css
✅ /fonts/font.woff
```

#### 场景2：同时访问视频和静态资源

```bash
# 添加路径白名单（用于视频）
POST /api/whitelist
{
  "uid": "user123",
  "path": "/video/abc123/playlist.m3u8",
  "clientIp": "192.168.1.100",
  "UserAgent": "Mozilla/5.0..."
}

# 添加静态文件白名单（用于静态资源）
POST /api/static-whitelist
{
  "uid": "user123",
  "clientIp": "192.168.2.200",  # 可以是不同IP
  "UserAgent": "Mozilla/5.0..."
}

# 结果：两个白名单独立工作
✅ 192.168.1.100 可以访问 /video/abc123/* 和静态文件
✅ 192.168.2.200 只能访问静态文件
```

#### 场景3：多设备访问

```bash
# 添加多个设备的UA+IP组合
POST /api/static-whitelist  # 手机
POST /api/static-whitelist  # 平板
POST /api/static-whitelist  # 电脑

# 每个设备都可以独立访问静态文件
# 最多支持 MAX_UA_IP_PAIRS_PER_UID 个组合
```

### 与原有API对比

| 特性 | /api/whitelist | /api/static-whitelist |
|------|----------------|----------------------|
| 需要path参数 | ✅ 必需 | ❌ 不需要 |
| Redis键前缀 | `ip_cidr_access:` | `static_file_access:` |
| UID追踪键 | `uid_ua_ip_pairs:` | `uid_static_ua_ip_pairs:` |
| 路径验证 | ✅ 验证 | ❌ 跳过 |
| 适用文件 | 视频、m3u8、ts | 静态文件（webp、jpg、css等） |
| 是否独立 | - | ✅ 完全独立 |
| FIFO替换 | ✅ 支持 | ✅ 支持 |
| TTL | `IP_ACCESS_TTL` | `IP_ACCESS_TTL` |

### 优势

1. **简化API调用**：无需提供path参数
2. **独立管理**：与路径白名单分离，互不干扰
3. **专用场景**：专门为静态文件设计
4. **灵活组合**：可以与路径白名单同时使用
5. **自动清理**：FIFO替换确保不会无限增长

## 版本历史

- **v2.2.0** (2024-11)
  - 新增静态文件专用白名单API (`/api/static-whitelist`)
  - 独立Redis键存储，支持多个UA+IP组合
  - 无需提供path参数，简化API调用
  
- **v2.1.0** (2024-11)
  - 添加多UA+IP对管理功能
  - 添加静态文件IP-only验证功能
  - 添加单元测试和集成测试
