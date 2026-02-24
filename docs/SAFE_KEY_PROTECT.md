# Safe Key Protect 功能说明

## 概述

Safe Key Protect（安全密钥保护）是一项安全增强功能，当已授权用户访问 `enc.key` 文件时，系统会自动将用户重定向到指定的安全路由，确保密钥文件通过安全通道传输。

## 功能特性

### 1. 智能重定向
- 仅对 `enc.key` 文件进行重定向处理
- 必须首先通过访问权限验证（IP白名单检查）
- 在访问被允许后重定向到安全路由

### 2. 可配置开关
- 通过配置项可以启用/禁用此功能
- 重定向URL可以自定义配置

### 3. 选择性触发
- 仅对以 `enc.key` 结尾的文件触发重定向
- 其他文件类型正常处理，不受影响
- 未授权访问仍返回403错误

## 配置选项

在 `OptimizedConfig` 类中添加了以下配置项：

```python
# Safe Key Protect 配置
SAFE_KEY_PROTECT_ENABLED = False  # 启用安全密钥保护重定向
SAFE_KEY_PROTECT_REDIRECT_BASE_URL = "https://v.yuelk.com/pyvideo2/keyroute/"  # 重定向基础URL
```

### 配置说明

- **SAFE_KEY_PROTECT_ENABLED**: 布尔值，控制是否启用Safe Key Protect功能
  - `True`: 启用，会进行重定向
  - `False`: 禁用，保持原有的403错误返回（默认）

- **SAFE_KEY_PROTECT_REDIRECT_BASE_URL**: 字符串，重定向的基础URL
  - 默认: `"https://v.yuelk.com/pyvideo2/keyroute/"`
  - 最终重定向URL将是: `基础URL + 原始访问路径`

## 工作流程

1. 用户访问 `enc.key` 文件（如: `wp-content/uploads/video/2025-08-30/4ad2ee3021_22U6pQ/720p_2e2809/enc.key`）

2. 系统检查用户IP是否在白名单中

3. 如果不在白名单中：
   - 返回403错误（访问被拒绝）

4. 如果在白名单中（访问被允许）：
   - **禁用Safe Key Protect**: 正常提供文件内容
   - **启用Safe Key Protect**: 重定向到安全路由
     - 重定向到: `https://v.yuelk.com/pyvideo2/keyroute/wp-content/uploads/video/2025-08-30/4ad2ee3021_22U6pQ/720p_2e2809/enc.key`

5. 对于非 `enc.key` 文件，不进行重定向处理

## 文件类型检测逻辑

系统检查请求路径是否以 `enc.key` 结尾：

- ✅ 触发重定向: `wp-content/uploads/video/2025-08-30/4ad2ee3021_22U6pQ/720p_2e2809/enc.key`
- ✅ 触发重定向: `some/path/to/enc.key`  
- ❌ 不触发重定向: `index.m3u8`
- ❌ 不触发重定向: `video.ts`
- ❌ 不触发重定向: `style.css`

## 日志记录

启用Safe Key Protect重定向时，系统会记录详细日志：

```
🔐 Safe Key Protect重定向: IP=192.168.1.1, enc.key文件=wp-content/uploads/video/2025-08-30/4ad2ee3021_22U6pQ/720p_2e2809/enc.key, redirect_to=https://v.yuelk.com/pyvideo2/keyroute/wp-content/uploads/video/2025-08-30/4ad2ee3021_22U6pQ/720p_2e2809/enc.key
```

## 启用方法

1. 修改配置文件或代码中的配置：
   ```python
   SAFE_KEY_PROTECT_ENABLED = True
   ```

2. 可选：自定义重定向URL：
   ```python
   SAFE_KEY_PROTECT_REDIRECT_BASE_URL = "https://yourdomain.com/secure/"
   ```

3. 重启应用服务

## 监控和调试

可以通过 `/health` 端点查看Safe Key Protect的配置状态：

```json
{
  "config": {
    "safe_key_protect_enabled": true,
    "safe_key_protect_redirect_url": "https://v.yuelk.com/pyvideo2/keyroute/"
  }
}
```

## 注意事项

1. **安全优先**: 必须首先通过IP白名单验证，重定向不会绕过访问控制
2. **文件类型限制**: 仅对 `enc.key` 文件生效，确保精确控制
3. **SEO友好**: 使用302重定向，对搜索引擎友好
4. **性能影响**: 启用此功能对性能影响极小
5. **兼容性**: 与现有CIDR IP匹配功能完全兼容