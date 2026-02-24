"""
浏览器检测工具
用于识别不同类型的浏览器和下载工具
"""
from typing import Tuple, Dict


class BrowserDetector:
    """浏览器类型检测器，用于识别不同浏览器的访问模式"""
    
    MOBILE_BROWSERS = {
        'qq': (['QQBrowser', 'MQQBrowser'], ['Mobile', 'Android', 'iPhone']),
        'uc': (['UCBrowser', 'UCWEB'], ['Mobile', 'Android', 'iPhone']),
        'baidu': (['baiduboxapp', 'BaiduHD'], ['Mobile', 'Android', 'iPhone']),
        'sogou': (['SogouMobileBrowser', 'SogouSearch'], ['Mobile', 'Android', 'iPhone']),
        'chrome_mobile': (['Chrome/'], ['Mobile', 'Android', 'iPhone']),
        'safari_mobile': (['Safari/'], ['Mobile', 'iPhone', 'iPad']),
        'edge_mobile': (['Edge/', 'EdgA/', 'EdgiOS/'], ['Mobile', 'Android', 'iPhone']),
        'firefox_mobile': (['Firefox/', 'FxiOS/'], ['Mobile', 'Android', 'iPhone'])
    }
    
    DESKTOP_BROWSERS = {
        'chrome': (['Chrome/'], ['Windows NT', 'Macintosh', 'X11; Linux']),
        'firefox': (['Firefox/'], ['Windows NT', 'Macintosh', 'X11; Linux']),
        'edge': (['Edge/', 'Edg/'], ['Windows NT', 'Macintosh']),
        'safari': (['Safari/', 'Version/'], ['Macintosh']),
        'opera': (['Opera/', 'OPR/'], ['Windows NT', 'Macintosh', 'X11; Linux'])
    }
    
    DOWNLOAD_TOOLS = [
        'wget', 'curl', 'aria2', 'axel', 'youtube-dl', 'yt-dlp',
        'ffmpeg', 'vlc', 'mpv', 'IDM', 'Thunder', 'BitComet',
        'uTorrent', 'qBittorrent', 'Transmission', 'Deluge',
        'FlashGet', 'FreeDownloadManager', 'EagleGet',
        'python-requests', 'urllib', 'httplib', 'Go-http-client',
        'node-fetch', 'axios', 'okhttp'
    ]
    
    @classmethod
    def detect_browser_type(cls, user_agent: str) -> Tuple[str, str, int]:
        """
        检测浏览器类型并返回相应的访问限制
        返回: (browser_type, browser_name, max_access_count)
        """
        if not user_agent:
            return "unknown", "unknown", 1
        
        user_agent_lower = user_agent.lower()
        
        # 检查下载工具
        for tool in cls.DOWNLOAD_TOOLS:
            if tool.lower() in user_agent_lower:
                return "download_tool", tool, 1
        
        # 检查移动浏览器
        for browser_name, (primary_keywords, platform_keywords) in cls.MOBILE_BROWSERS.items():
            has_primary = any(keyword.lower() in user_agent_lower for keyword in primary_keywords)
            has_platform = any(keyword.lower() in user_agent_lower for keyword in platform_keywords)
            
            if has_primary and has_platform:
                if browser_name in ['qq', 'uc']:
                    return "mobile_browser", browser_name, 3
                else:
                    return "mobile_browser", browser_name, 2
        
        # 检查桌面浏览器
        for browser_name, (primary_keywords, platform_keywords) in cls.DESKTOP_BROWSERS.items():
            has_primary = any(keyword.lower() in user_agent_lower for keyword in primary_keywords)
            has_platform = any(keyword.lower() in user_agent_lower for keyword in platform_keywords)
            
            if has_primary and has_platform:
                return "desktop_browser", browser_name, 2
        
        # 通用浏览器检测
        if any(keyword in user_agent_lower for keyword in ['mozilla', 'webkit', 'chrome', 'safari', 'firefox', 'edge']):
            if any(keyword in user_agent_lower for keyword in ['mobile', 'android', 'iphone', 'ipad']):
                return "mobile_browser", "generic_mobile", 2
            else:
                return "desktop_browser", "generic_desktop", 2
        
        return "unknown", "unknown", 1
    
    @classmethod
    def debug_detection(cls, user_agent: str) -> Dict:
        """调试用函数，返回详细的检测信息"""
        if not user_agent:
            return {"error": "Empty user agent"}
        
        user_agent_lower = user_agent.lower()
        debug_info = {
            "user_agent": user_agent,
            "download_tools_found": [],
            "mobile_browser_matches": {},
            "desktop_browser_matches": {},
            "final_result": None
        }
        
        # 检查下载工具
        for tool in cls.DOWNLOAD_TOOLS:
            if tool.lower() in user_agent_lower:
                debug_info["download_tools_found"].append(tool)
        
        # 检查移动浏览器
        for browser_name, (primary_keywords, platform_keywords) in cls.MOBILE_BROWSERS.items():
            primary_matches = [kw for kw in primary_keywords if kw.lower() in user_agent_lower]
            platform_matches = [kw for kw in platform_keywords if kw.lower() in user_agent_lower]
            
            if primary_matches or platform_matches:
                debug_info["mobile_browser_matches"][browser_name] = {
                    "primary_keywords": primary_matches,
                    "platform_keywords": platform_matches,
                    "has_both": bool(primary_matches and platform_matches)
                }
        
        # 检查桌面浏览器
        for browser_name, (primary_keywords, platform_keywords) in cls.DESKTOP_BROWSERS.items():
            primary_matches = [kw for kw in primary_keywords if kw.lower() in user_agent_lower]
            platform_matches = [kw for kw in platform_keywords if kw.lower() in user_agent_lower]
            
            if primary_matches or platform_matches:
                debug_info["desktop_browser_matches"][browser_name] = {
                    "primary_keywords": primary_matches,
                    "platform_keywords": platform_matches,
                    "has_both": bool(primary_matches and platform_matches)
                }
        
        debug_info["final_result"] = cls.detect_browser_type(user_agent)
        
        return debug_info
