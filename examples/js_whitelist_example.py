#!/usr/bin/env python3
"""
JS白名单追踪功能使用示例
JavaScript Whitelist Tracker Usage Example

展示如何使用JS白名单追踪功能，包括：
1. 添加JS文件到白名单（API Key方式 - 后端服务器）
2. 添加JS文件到白名单（HMAC签名方式 - 前端）
3. 验证JS文件访问权限
4. 查看白名单统计信息
"""

import requests
import json
import hashlib
import hmac
import time

# 配置
BASE_URL = "http://localhost:7889"
API_KEY = "F2UkWEJZRBxC7"  # 从 config.py 获取（仅后端服务器使用）
JS_WHITELIST_SECRET_KEY = b"js_whitelist_secret_key_change_this"  # 从 config.py 的 JS_WHITELIST_SECRET_KEY 获取
JS_WHITELIST_SIGNATURE_TTL = 60 * 60  # 签名有效期：1小时（从 config.py 的 JS_WHITELIST_SIGNATURE_TTL 获取）


def generate_hmac_signature(uid, js_path, expires, secret_key):
    """
    生成HMAC签名
    
    Args:
        uid: 用户ID
        js_path: JS文件路径
        expires: 过期时间戳
        secret_key: 密钥
    
    Returns:
        签名字符串
    """
    # 构建待签名字符串: uid:path:expires
    message = f"{uid}:{js_path}:{expires}"
    
    # 使用HMAC-SHA256生成签名
    signature = hmac.new(
        secret_key,
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature


def add_js_to_whitelist_with_api_key(uid, js_path):
    """
    使用API Key添加JS文件到白名单（后端服务器调用）
    
    注意：UA和IP会自动从请求中获取，无需手动传递
    """
    url = f"{BASE_URL}/api/js-whitelist"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "uid": uid,
        "jsPath": js_path
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        if hasattr(e, 'response') and e.response:
            print(f"   响应: {e.response.text}")
        return None


def add_js_to_whitelist_with_signature(uid, js_path, use_get=True):
    """
    使用HMAC签名添加JS文件到白名单（前端调用）
    
    这种方式不暴露API Key，适合前端使用
    注意：UA和IP会自动从请求中获取，无需手动传递
    
    Args:
        uid: 用户ID
        js_path: JS文件路径
        use_get: 是否使用GET方法（默认True），False则使用POST
    """
    # 生成过期时间（使用配置的签名有效期，默认1小时）
    expires = str(int(time.time()) + JS_WHITELIST_SIGNATURE_TTL)
    
    # 生成HMAC签名 - 使用JS白名单专用密钥
    signature = generate_hmac_signature(uid, js_path, expires, JS_WHITELIST_SECRET_KEY)
    
    # 构建请求URL（使用查询参数）
    url = f"{BASE_URL}/api/js-whitelist"
    params = {
        "uid": uid,
        "js_path": js_path,
        "expires": expires,
        "sign": signature
    }
    
    try:
        # 使用GET或POST方法
        if use_get:
            response = requests.get(url, params=params)
        else:
            response = requests.post(url, params=params)
        
        response.raise_for_status()
        result = response.json()
        return result
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        if hasattr(e, 'response') and e.response:
            print(f"   响应: {e.response.text}")
        return None


def add_js_to_whitelist(uid, js_path, use_signature=False):
    """
    添加JS文件到白名单（包装函数）
    
    Args:
        uid: 用户ID
        js_path: JS文件路径
        use_signature: 是否使用签名方式（True=前端，False=后端API Key）
    """
    if use_signature:
        return add_js_to_whitelist_with_signature(uid, js_path)
    else:
        return add_js_to_whitelist_with_api_key(uid, js_path)


def check_js_whitelist(js_path, uid=None):
    """
    检查JS文件访问权限
    
    UA和IP会自动从请求中获取
    """
    url = f"{BASE_URL}/api/js-whitelist/check"
    params = {"js_path": js_path}
    if uid:
        params["uid"] = uid
    
    try:
        response = requests.get(url, params=params)
        result = response.json()
        return result
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return None


def get_js_whitelist_stats(uid):
    """获取JS白名单统计信息"""
    url = f"{BASE_URL}/api/js-whitelist/stats"
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    params = {"uid": uid}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        result = response.json()
        return result
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return None


def access_js_file(js_path):
    """尝试访问JS文件"""
    url = f"{BASE_URL}/{js_path}"
    
    try:
        response = requests.get(url)
        return {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "content_length": len(response.content) if response.status_code == 200 else 0
        }
    except Exception as e:
        print(f"❌ 访问失败: {str(e)}")
        return {
            "status_code": 0,
            "success": False,
            "error": str(e)
        }


def example_basic_usage():
    """示例1：基本使用流程"""
    print("=" * 70)
    print("示例1：JS白名单追踪 - 基本使用流程")
    print("=" * 70)
    
    uid = "demo_user_js_001"
    js_path = "static/js/app.js"
    
    print(f"\n场景设置:")
    print(f"  用户ID: {uid}")
    print(f"  JS文件: {js_path}")
    print(f"  说明: UA和IP会自动从本服务器的请求中获取")
    
    # 步骤1: 添加到白名单
    print(f"\n步骤1: 添加JS文件到白名单")
    print(f"  调用: POST /api/js-whitelist")
    print(f"  参数: {{'uid': '{uid}', 'jsPath': '{js_path}'}}")
    
    result = add_js_to_whitelist(uid, js_path)
    
    if result and result.get("success"):
        print("  ✅ 添加成功")
        data = result.get("data", {})
        print(f"     - UID: {data.get('uid')}")
        print(f"     - JS路径: {data.get('js_path')}")
        print(f"     - 客户端IP: {data.get('client_ip')}")
        print(f"     - TTL: {data.get('ttl')} 秒")
        print(f"     - 过期时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(data.get('expires_at', 0)))}")
    else:
        print(f"  ❌ 添加失败: {result.get('error') if result else '未知错误'}")
        return
    
    # 步骤2: 验证访问权限
    print(f"\n步骤2: 验证访问权限")
    print(f"  调用: GET /api/js-whitelist/check?js_path={js_path}")
    
    check_result = check_js_whitelist(js_path)
    
    if check_result:
        is_allowed = check_result.get("is_allowed")
        print(f"  {'✅' if is_allowed else '❌'} 验证结果: {'允许访问' if is_allowed else '拒绝访问'}")
        print(f"     - JS路径: {check_result.get('js_path')}")
        print(f"     - UID: {check_result.get('uid')}")
        print(f"     - 客户端IP: {check_result.get('client_ip')}")
    
    # 步骤3: 查看统计信息
    print(f"\n步骤3: 查看白名单统计信息")
    print(f"  调用: GET /api/js-whitelist/stats?uid={uid}")
    
    stats = get_js_whitelist_stats(uid)
    
    if stats and stats.get("enabled"):
        print(f"  ✅ 统计信息:")
        print(f"     - 启用状态: {stats.get('enabled')}")
        print(f"     - 用户ID: {stats.get('uid')}")
        print(f"     - 总记录数: {stats.get('total_entries')}")
        print(f"     - TTL配置: {stats.get('ttl_config')} 秒")
        
        entries = stats.get("entries", [])
        if entries:
            print(f"\n     白名单记录:")
            for i, entry in enumerate(entries, 1):
                print(f"     [{i}] {entry.get('js_path')}")
                print(f"         IP: {entry.get('client_ip')}")
                print(f"         剩余TTL: {entry.get('remaining_ttl')} 秒")
    
    print("\n" + "=" * 70)
    print("✅ 示例1完成")
    print("=" * 70)


def example_signature_auth():
    """示例1.5：使用HMAC签名认证（前端安全方式）"""
    print("\n\n" + "=" * 70)
    print("示例1.5：HMAC签名认证 - 前端安全调用方式")
    print("=" * 70)
    
    uid = "demo_user_js_frontend"
    js_path = "static/js/frontend_app.js"
    
    print(f"\n场景设置:")
    print(f"  用户ID: {uid}")
    print(f"  JS文件: {js_path}")
    print(f"  认证方式: HMAC签名（不暴露API Key）")
    
    # 步骤1: 生成签名并添加到白名单
    print(f"\n步骤1: 使用HMAC签名添加JS文件到白名单")
    print(f"  说明: 适合前端调用，不暴露API Key")
    print(f"  方法: GET或POST都支持，GET更简单可直接访问URL")
    print(f"  签名有效期: {JS_WHITELIST_SIGNATURE_TTL} 秒（{JS_WHITELIST_SIGNATURE_TTL // 60} 分钟）")
    
    expires = int(time.time()) + JS_WHITELIST_SIGNATURE_TTL
    signature = generate_hmac_signature(uid, js_path, str(expires), JS_WHITELIST_SECRET_KEY)
    
    print(f"\n  生成的签名信息:")
    print(f"     - UID: {uid}")
    print(f"     - JS路径: {js_path}")
    print(f"     - 过期时间: {expires} ({time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expires))})")
    print(f"     - 签名: {signature[:20]}...")
    
    # 构建完整URL供直接访问
    full_url = f"{BASE_URL}/api/js-whitelist?uid={uid}&js_path={js_path}&expires={expires}&sign={signature}"
    print(f"\n  完整URL（可直接在浏览器访问）:")
    print(f"     {full_url}")
    
    print(f"\n  调用API (使用GET方法)...")
    
    result = add_js_to_whitelist(uid, js_path, use_signature=True)
    
    if result and result.get("success"):
        print("  ✅ 添加成功（使用签名认证）")
        data = result.get("data", {})
        print(f"     - 客户端IP: {data.get('client_ip')}")
        print(f"     - TTL: {data.get('ttl')} 秒")
    else:
        print(f"  ❌ 添加失败: {result.get('error') if result else '未知错误'}")
    
    # 步骤2: 展示JavaScript代码示例
    print(f"\n步骤2: 前端JavaScript调用示例")
    
    js_code = f'''
// 前端JavaScript代码 - 安全调用示例
async function addJSToWhitelist(uid, jsPath) {{
    // 1. 从服务器获取签名（后端生成签名，避免暴露JS_WHITELIST_SECRET_KEY）
    const signResponse = await fetch('/api/generate-js-signature', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ uid, jsPath }})
    }});
    
    const {{ expires, signature }} = await signResponse.json();
    
    // 2. 使用签名调用白名单API
    const whitelistUrl = new URL('http://fileproxy-server:7889/api/js-whitelist');
    whitelistUrl.searchParams.set('uid', uid);
    whitelistUrl.searchParams.set('js_path', jsPath);
    whitelistUrl.searchParams.set('expires', expires);
    whitelistUrl.searchParams.set('sign', signature);
    
    const response = await fetch(whitelistUrl, {{
        method: 'POST'
    }});
    
    return await response.json();
}}

// 使用示例
addJSToWhitelist('{uid}', '{js_path}')
    .then(result => console.log('已添加到白名单:', result))
    .catch(err => console.error('添加失败:', err));
'''
    
    print(js_code)
    
    print("\n" + "=" * 70)
    print("✅ 示例1.5完成")
    print("=" * 70)


def example_html_integration():
    """示例2：HTML页面集成示例"""
    print("\n\n" + "=" * 70)
    print("示例2：HTML页面集成 - 异步非阻塞模式")
    print("=" * 70)
    
    print("\n完整的调用示例：")
    print("\n1. 服务器端：添加JS文件到白名单（使用API Key）")
    print("   使用远程API调用（例如从你的主服务器）：")
    print("""
   POST http://fileproxy-server:7889/api/js-whitelist
   Headers:
       Authorization: Bearer F2UkWEJZRBxC7
       Content-Type: application/json
   Body:
       {
           "uid": "user_12345",
           "jsPath": "static/js/app.js"
       }
   
   注意：UA和IP会自动从发起请求的客户端获取
   """)
    
    print("\n2. 前端：使用HMAC签名添加（不暴露API Key）")
    print("""
   POST http://fileproxy-server:7889/api/js-whitelist?uid=user123&js_path=static/js/app.js&expires=1234567890&sign=xxx
   
   签名生成（在你的主服务器上）:
       message = "uid:js_path:expires"
       signature = HMAC-SHA256(SECRET_KEY, message)
   
   这样前端可以安全调用，不会暴露API Key或SECRET_KEY
   """)
    
    print("\n2. 客户端：在HTML页面中引用JS文件")
    print("   使用异步非阻塞模式（defer）：")
    
    html_example = """
   <!DOCTYPE html>
   <html>
   <head>
       <meta charset="UTF-8">
       <title>JS白名单示例</title>
   </head>
   <body>
       <h1>JS白名单追踪示例</h1>
       
       <!-- 方式1: 使用defer异步加载（推荐） -->
       <script defer src="http://fileproxy-server:7889/static/js/app.js"></script>
       
       <!-- 方式2: 使用async异步加载 -->
       <script async src="http://fileproxy-server:7889/static/js/utils.js"></script>
       
       <!-- 方式3: 普通同步加载 -->
       <script src="http://fileproxy-server:7889/static/js/main.js"></script>
       
       <p>
           说明：
           - defer: 延迟执行，按顺序加载，不阻塞页面解析
           - async: 异步加载，加载完立即执行，可能乱序
           - 普通: 同步加载，会阻塞页面解析
       </p>
   </body>
   </html>
   """
    print(html_example)
    
    print("\n3. 访问流程说明：")
    print("   ① 用户访问HTML页面")
    print("   ② 浏览器解析到<script>标签，发起JS文件请求")
    print("   ③ FileProxy服务器接收请求，自动提取UA和IP")
    print("   ④ 验证UA+IP是否在白名单中")
    print("   ⑤ 如果在白名单中，返回JS文件内容")
    print("   ⑥ 如果不在白名单中，返回403 Forbidden")
    
    print("\n" + "=" * 70)
    print("✅ 示例2完成")
    print("=" * 70)


def example_multiple_js_files():
    """示例3：多个JS文件管理"""
    print("\n\n" + "=" * 70)
    print("示例3：管理多个JS文件")
    print("=" * 70)
    
    uid = "demo_user_js_002"
    js_files = [
        "static/js/jquery.min.js",
        "static/js/bootstrap.min.js",
        "static/js/app.js",
        "static/js/utils.js"
    ]
    
    print(f"\n用户ID: {uid}")
    print(f"将添加 {len(js_files)} 个JS文件到白名单\n")
    
    for i, js_path in enumerate(js_files, 1):
        print(f"\n[{i}/{len(js_files)}] 添加: {js_path}")
        result = add_js_to_whitelist(uid, js_path)
        
        if result and result.get("success"):
            print(f"  ✅ 成功")
        else:
            print(f"  ❌ 失败: {result.get('error') if result else '未知错误'}")
    
    # 查看统计
    print(f"\n查看用户的白名单统计:")
    stats = get_js_whitelist_stats(uid)
    
    if stats and stats.get("enabled"):
        print(f"  总记录数: {stats.get('total_entries')}")
        print(f"  记录列表:")
        for entry in stats.get("entries", []):
            print(f"    - {entry.get('js_path')} (剩余TTL: {entry.get('remaining_ttl')}s)")
    
    print("\n" + "=" * 70)
    print("✅ 示例3完成")
    print("=" * 70)


def example_auto_ua_ip():
    """示例4：自动UA和IP获取演示"""
    print("\n\n" + "=" * 70)
    print("示例4：自动UA和IP获取机制")
    print("=" * 70)
    
    print("\n特性说明：")
    print("  ✅ UA (User-Agent) 自动从 HTTP 请求头中获取")
    print("  ✅ IP 自动从请求中提取（支持X-Forwarded-For）")
    print("  ✅ 无需在JS代码中传递敏感信息")
    print("  ✅ 提高安全性，防止伪造")
    
    print("\n实现原理：")
    print("  1. 客户端浏览器发起请求")
    print("  2. 服务器从请求头中提取：")
    print("     - User-Agent: request.headers.get('User-Agent')")
    print("     - Client-IP: get_client_ip(request)")
    print("  3. 使用提取的UA+IP创建白名单记录")
    print("  4. 后续访问时，使用相同的方法验证")
    
    print("\n优势：")
    print("  ✅ 简化客户端代码，无需获取UA/IP")
    print("  ✅ 防止客户端伪造UA/IP信息")
    print("  ✅ 服务器端完全控制，更安全")
    print("  ✅ 透明化处理，开发者无感知")
    
    print("\n示例代码（Python客户端）：")
    code_example = '''
# 添加JS文件到白名单 - 极简调用
import requests

response = requests.post(
    'http://fileproxy-server:7889/api/js-whitelist',
    headers={
        'Authorization': 'Bearer YOUR_API_KEY',
        'Content-Type': 'application/json'
    },
    json={
        'uid': 'user123',
        'jsPath': 'static/js/app.js'
    }
)

# 就这么简单！UA和IP会自动被服务器捕获
'''
    print(code_example)
    
    print("\n" + "=" * 70)
    print("✅ 示例4完成")
    print("=" * 70)


def main():
    """主函数"""
    print("\n")
    print("*" * 70)
    print("JS白名单追踪功能 - 完整使用示例")
    print("*" * 70)
    
    print("\n功能特性：")
    print("  ✅ 追踪JS文件访问，基于UA+IP白名单")
    print("  ✅ 可在config.py中完全开启/关闭")
    print("  ✅ 自动从请求中获取UA和IP，无需JS传输")
    print("  ✅ 支持异步非阻塞模式（defer/async）")
    print("  ✅ 配置化TTL管理（默认60分钟）")
    print("  ✅ 双重认证方式：API Key（后端）+ HMAC签名（前端）")
    
    print("\n配置项（config.py）：")
    print("  ENABLE_JS_WHITELIST_TRACKER = True")
    print("  JS_WHITELIST_TRACKER_TTL = 60 * 60  # 追踪记录TTL：60分钟")
    print("  JS_WHITELIST_SECRET_KEY = b'...'  # JS白名单HMAC签名密钥（独立配置）")
    print("  JS_WHITELIST_SIGNATURE_TTL = 60 * 60  # 签名有效期：1小时")
    
    print("\n认证方式：")
    print("  1. API Key: 适合后端服务器调用（需要Authorization头）")
    print("  2. HMAC签名: 适合前端调用（不暴露API Key）")
    print("     - 使用独立的 JS_WHITELIST_SECRET_KEY")
    print("     - 签名有效期1小时（可配置）")
    
    print("\n提示：")
    print("  1. 确保FileProxy服务器运行在 http://localhost:7889")
    print("  2. API_KEY 和 JS_WHITELIST_SECRET_KEY 需要与 config.py 中匹配")
    print("  3. 在config.py中启用JS白名单追踪功能")
    print("  4. 前端调用使用HMAC签名，后端调用使用API Key")
    print("  5. 签名有效期为1小时，确保及时生成新签名")
    
    response = input("\n是否继续运行示例？(y/n): ")
    if response.lower() != 'y':
        print("已取消")
        return
    
    try:
        # 运行所有示例
        example_basic_usage()
        example_signature_auth()  # 新增：签名认证示例
        example_html_integration()
        example_multiple_js_files()
        example_auto_ua_ip()
        
        print("\n\n" + "*" * 70)
        print("所有示例完成！")
        print("*" * 70)
        print("\n更多信息：")
        print("  - API文档: http://localhost:7889/docs")
        print("  - 监控面板: http://localhost:7889/monitor")
        print("  - 配置文件: models/config.py")
        print("\n认证方式总结：")
        print("  - 后端服务器: 使用 API Key (Authorization: Bearer xxx)")
        print("  - 前端调用: 使用 HMAC 签名 (?uid=xxx&js_path=xxx&expires=xxx&sign=xxx)")
        
    except KeyboardInterrupt:
        print("\n\n已中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
