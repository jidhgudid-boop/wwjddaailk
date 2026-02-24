#!/usr/bin/env python3
"""
Key 文件动态保护服务单元测试
Test Key Protection Service
"""

import pytest
import asyncio
import hashlib
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

# Add the FileProxy directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestModifyM3u8KeyUri:
    """测试 m3u8 内容动态修改"""
    
    def test_modify_basic_key_uri(self):
        """测试基本的 key URI 修改"""
        from services.key_protect_service import modify_m3u8_key_uri
        
        original = '''#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:8
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-KEY:METHOD=AES-128,URI="enc.key",IV=0x25534c1aadaa025d47ff326258308d70
#EXTINF:8.0,
segment0.ts
#EXTINF:8.0,
segment1.ts
#EXT-X-ENDLIST'''
        
        secret_key = b"test_secret_key"
        modified = modify_m3u8_key_uri(
            m3u8_content=original,
            uid="315",
            expires="1700000000",
            secret_key=secret_key,
            m3u8_dir="video/test"
        )
        
        # 验证 URI 被修改，包含 uid 和 expires
        assert 'uid=315' in modified
        assert 'expires=1700000000' in modified
        assert 'token=' in modified  # token 是动态生成的
        # 验证其他内容保持不变
        assert '#EXT-X-VERSION:3' in modified
        assert '#EXT-X-TARGETDURATION:8' in modified
        assert 'segment0.ts' in modified
        assert 'IV=0x25534c1aadaa025d47ff326258308d70' in modified
    
    def test_modify_key_uri_with_path(self):
        """测试带路径的 key URI 修改"""
        from services.key_protect_service import modify_m3u8_key_uri
        
        original = '#EXT-X-KEY:METHOD=AES-128,URI="path/to/enc.key"'
        
        secret_key = b"test_secret_key"
        modified = modify_m3u8_key_uri(
            m3u8_content=original,
            uid="123",
            expires="9999999999",
            secret_key=secret_key,
            m3u8_dir=""
        )
        
        assert 'uid=123' in modified
        assert 'expires=9999999999' in modified
        assert 'token=' in modified
    
    def test_modify_key_uri_single_quotes(self):
        """测试单引号的 key URI 修改"""
        from services.key_protect_service import modify_m3u8_key_uri
        
        original = "#EXT-X-KEY:METHOD=AES-128,URI='enc.key'"
        
        secret_key = b"test_secret_key"
        modified = modify_m3u8_key_uri(
            m3u8_content=original,
            uid="123",
            expires="9999999999",
            secret_key=secret_key,
            m3u8_dir=""
        )
        
        assert "uid=123" in modified
        assert "token=" in modified
    
    def test_modify_multiple_key_uris(self):
        """测试多个 key URI 的修改"""
        from services.key_protect_service import modify_m3u8_key_uri
        
        original = '''#EXTM3U
#EXT-X-KEY:METHOD=AES-128,URI="key1.key"
#EXTINF:8.0,
segment0.ts
#EXT-X-KEY:METHOD=AES-128,URI="key2.key"
#EXTINF:8.0,
segment1.ts'''
        
        secret_key = b"test_secret_key"
        modified = modify_m3u8_key_uri(
            m3u8_content=original,
            uid="315",
            expires="1700000000",
            secret_key=secret_key,
            m3u8_dir=""
        )
        
        # 两个 key URI 都应该被修改
        assert 'key1.key?uid=315' in modified
        assert 'key2.key?uid=315' in modified
    
    def test_modify_empty_content(self):
        """测试空内容"""
        from services.key_protect_service import modify_m3u8_key_uri
        
        secret_key = b"test_secret_key"
        result = modify_m3u8_key_uri("", "123", "9999", secret_key, "")
        assert result == ""
        
        result = modify_m3u8_key_uri(None, "123", "9999", secret_key, "")
        assert result is None
    
    def test_modify_uri_with_existing_params(self):
        """测试已有查询参数的 URI 修改"""
        from services.key_protect_service import modify_m3u8_key_uri
        
        original = '#EXT-X-KEY:METHOD=AES-128,URI="enc.key?existing=param"'
        
        secret_key = b"test_secret_key"
        modified = modify_m3u8_key_uri(
            m3u8_content=original,
            uid="123",
            expires="9999999999",
            secret_key=secret_key,
            m3u8_dir=""
        )
        
        # 应该追加参数而不是替换
        assert 'enc.key?existing=param&uid=123' in modified
        assert 'token=' in modified
    
    def test_modify_only_ext_x_key_uri(self):
        """测试只修改 EXT-X-KEY 标签的 URI，不影响其他标签"""
        from services.key_protect_service import modify_m3u8_key_uri
        
        original = '''#EXTM3U
#EXT-X-MAP:URI="init.mp4"
#EXT-X-KEY:METHOD=AES-128,URI="enc.key"
#EXTINF:8.0,
segment0.ts'''
        
        secret_key = b"test_secret_key"
        modified = modify_m3u8_key_uri(
            m3u8_content=original,
            uid="123",
            expires="9999999999",
            secret_key=secret_key,
            m3u8_dir=""
        )
        
        # EXT-X-KEY 的 URI 应该被修改
        assert 'enc.key?uid=123' in modified
        # EXT-X-MAP 的 URI 不应该被修改
        assert '#EXT-X-MAP:URI="init.mp4"' in modified


class TestGenerateKeyToken:
    """测试 key 文件独立 token 生成"""
    
    def test_generate_key_token(self):
        """测试生成 key 文件的独立 HMAC token"""
        from services.key_protect_service import generate_key_token
        
        secret_key = b"test_secret_key"
        uid = "123"
        key_path = "video/test/enc.key"
        expires = "9999999999"
        
        token = generate_key_token(uid, key_path, expires, secret_key)
        
        # 验证 token 是有效的十六进制字符串
        assert len(token) == 64  # SHA256 hexdigest 长度
        assert all(c in '0123456789abcdef' for c in token)
    
    def test_token_consistency(self):
        """测试相同参数生成相同 token"""
        from services.key_protect_service import generate_key_token
        
        secret_key = b"test_secret_key"
        uid = "123"
        key_path = "video/test/enc.key"
        expires = "9999999999"
        
        token1 = generate_key_token(uid, key_path, expires, secret_key)
        token2 = generate_key_token(uid, key_path, expires, secret_key)
        
        assert token1 == token2
    
    def test_token_uniqueness(self):
        """测试不同路径生成不同 token"""
        from services.key_protect_service import generate_key_token
        
        secret_key = b"test_secret_key"
        uid = "123"
        expires = "9999999999"
        
        token1 = generate_key_token(uid, "video/test1/enc.key", expires, secret_key)
        token2 = generate_key_token(uid, "video/test2/enc.key", expires, secret_key)
        
        assert token1 != token2
    
    def test_token_validation_compatible(self):
        """测试生成的 token 可以通过 HMAC 验证"""
        from services.key_protect_service import generate_key_token
        import hmac
        import hashlib
        
        secret_key = b"test_secret_key"
        uid = "123"
        key_path = "video/test/enc.key"
        expires = "9999999999"  # 远未来时间
        
        token = generate_key_token(uid, key_path, expires, secret_key)
        
        # 手动计算期望的 HMAC 来验证
        msg = f"{uid}:{key_path}:{expires}".encode()
        expected_token = hmac.new(secret_key, msg, hashlib.sha256).hexdigest()
        
        assert token == expected_token


class TestKeyProtectService:
    """Key 文件动态保护服务测试套件"""
    
    @pytest.fixture
    def mock_redis_client(self):
        """创建模拟的 Redis 客户端"""
        client = AsyncMock()
        client.incr = AsyncMock()
        client.expire = AsyncMock()
        client.ttl = AsyncMock()
        client.get = AsyncMock()
        client.setex = AsyncMock()
        client.delete = AsyncMock()
        client.lrange = AsyncMock()
        client.llen = AsyncMock()
        
        # Mock pipeline
        pipeline = AsyncMock()
        pipeline.lpush = MagicMock(return_value=pipeline)
        pipeline.ltrim = MagicMock(return_value=pipeline)
        pipeline.expire = MagicMock(return_value=pipeline)
        pipeline.execute = AsyncMock(return_value=[1, True, True])
        client.pipeline = MagicMock(return_value=pipeline)
        
        return client
    
    @pytest.fixture
    def mock_redis_service(self, mock_redis_client):
        """创建模拟的 Redis 服务"""
        service = MagicMock()
        service.get_client = MagicMock(return_value=mock_redis_client)
        return service
    
    def test_is_key_file(self):
        """测试密钥文件检测"""
        from services.key_protect_service import is_key_file
        
        extensions = ('.key', 'enc.key')
        
        # 应该匹配
        assert is_key_file("video/enc.key", extensions) is True
        assert is_key_file("path/to/file.key", extensions) is True
        assert is_key_file("ENC.KEY", extensions) is True  # 大小写不敏感
        
        # 不应该匹配
        assert is_key_file("video/index.m3u8", extensions) is False
        assert is_key_file("video/segment.ts", extensions) is False
        assert is_key_file("", extensions) is False
        assert is_key_file(None, extensions) is False
    
    @pytest.mark.asyncio
    async def test_check_key_access_first_use(self, mock_redis_service, mock_redis_client):
        """测试 key 文件首次访问"""
        mock_redis_client.incr.return_value = 1  # 首次访问
        
        import services.key_protect_service as key_protect_module
        
        with patch.object(key_protect_module, 'redis_service', mock_redis_service):
            allowed, info = await key_protect_module.check_key_access(
                key_path="wp-content/uploads/video/2025-08-30/test/720p/enc.key",
                uid="user_123",
                token="test_token_123",
                client_ip="192.168.1.1",
                max_uses=1,
                ttl=600
            )
            
            # 验证结果
            assert allowed is True
            assert info["is_first_use"] is True
            assert info["current_count"] == 1
            assert info["max_uses"] == 1
            assert info["remaining_uses"] == 0
    
    @pytest.mark.asyncio
    async def test_check_key_access_exceeded(self, mock_redis_service, mock_redis_client):
        """测试 key 文件访问次数超限（默认只允许1次）"""
        mock_redis_client.incr.return_value = 2  # 第二次访问
        mock_redis_client.ttl.return_value = 300
        
        import services.key_protect_service as key_protect_module
        
        with patch.object(key_protect_module, 'redis_service', mock_redis_service):
            allowed, info = await key_protect_module.check_key_access(
                key_path="wp-content/uploads/video/2025-08-30/test/720p/enc.key",
                uid="user_123",
                token="test_token_123",
                client_ip="192.168.1.1",
                max_uses=1,  # 只允许1次
                ttl=600
            )
            
            # 验证被拒绝
            assert allowed is False
            assert info["exceeded"] is True
            assert info["current_count"] == 2
            assert info["max_uses"] == 1
            assert info["remaining_uses"] == 0
    
    @pytest.mark.asyncio
    async def test_check_key_access_within_limit(self, mock_redis_service, mock_redis_client):
        """测试 key 文件访问在限制范围内"""
        mock_redis_client.incr.return_value = 2  # 第二次访问
        mock_redis_client.ttl.return_value = 400
        
        import services.key_protect_service as key_protect_module
        
        with patch.object(key_protect_module, 'redis_service', mock_redis_service):
            allowed, info = await key_protect_module.check_key_access(
                key_path="wp-content/uploads/video/2025-08-30/test/720p/enc.key",
                uid="user_123",
                token="test_token_123",
                client_ip="192.168.1.1",
                max_uses=3,  # 允许3次
                ttl=600
            )
            
            # 验证允许访问
            assert allowed is True
            assert info["current_count"] == 2
            assert info["max_uses"] == 3
            assert info["remaining_uses"] == 1
    
    @pytest.mark.asyncio
    async def test_check_key_access_redis_error(self, mock_redis_service, mock_redis_client):
        """测试 Redis 错误时的回退行为"""
        # 模拟 Redis 错误
        mock_redis_client.incr.side_effect = Exception("Redis connection error")
        
        import services.key_protect_service as key_protect_module
        
        with patch.object(key_protect_module, 'redis_service', mock_redis_service):
            allowed, info = await key_protect_module.check_key_access(
                key_path="wp-content/uploads/video/2025-08-30/test/720p/enc.key",
                uid="user_123",
                token="test_token_123",
                client_ip="192.168.1.1",
                max_uses=1,
                ttl=600
            )
            
            # Redis 错误时应该允许访问（避免服务不可用）
            assert allowed is True
            assert info["fallback"] is True
            assert "error" in info


class TestKeyProtectConfig:
    """Key 保护配置测试"""
    
    def test_config_defaults(self):
        """测试配置默认值"""
        from models.config import Config
        
        # 验证新配置项存在
        assert hasattr(Config, 'KEY_PROTECT_ENABLED')
        assert hasattr(Config, 'KEY_PROTECT_DYNAMIC_M3U8')
        assert hasattr(Config, 'KEY_PROTECT_MAX_USES')
        assert hasattr(Config, 'KEY_PROTECT_TTL')
        assert hasattr(Config, 'KEY_PROTECT_EXTENSIONS')
        
        # 验证默认值
        assert Config.KEY_PROTECT_ENABLED is True
        assert Config.KEY_PROTECT_DYNAMIC_M3U8 is True
        assert Config.KEY_PROTECT_MAX_USES == 1  # 默认只允许1次
        assert Config.KEY_PROTECT_TTL == 9600  # 约160分钟
        assert '.key' in Config.KEY_PROTECT_EXTENSIONS
        assert 'enc.key' in Config.KEY_PROTECT_EXTENSIONS
        
        # 验证 M3U8 缓存配置
        assert hasattr(Config, 'M3U8_CONTENT_CACHE_ENABLED')
        assert hasattr(Config, 'M3U8_CONTENT_CACHE_TTL')
        assert Config.M3U8_CONTENT_CACHE_ENABLED is True
        assert Config.M3U8_CONTENT_CACHE_TTL == 3600  # 1小时


class TestM3u8ContentCache:
    """M3U8 内容缓存测试"""
    
    @pytest.fixture
    def mock_redis_client(self):
        """创建模拟的 Redis 客户端"""
        client = AsyncMock()
        client.get = AsyncMock()
        client.setex = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_redis_service(self, mock_redis_client):
        """创建模拟的 Redis 服务"""
        service = MagicMock()
        service.get_client = MagicMock(return_value=mock_redis_client)
        return service
    
    @pytest.mark.asyncio
    async def test_get_cached_m3u8_content_hit(self, mock_redis_service, mock_redis_client):
        """测试缓存命中"""
        cached_content = "#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI=\"enc.key\""
        mock_redis_client.get.return_value = cached_content.encode('utf-8')
        
        import services.key_protect_service as key_protect_module
        
        with patch.object(key_protect_module, 'redis_service', mock_redis_service):
            result = await key_protect_module.get_cached_m3u8_content("video/test.m3u8")
            
            assert result == cached_content
            mock_redis_client.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_cached_m3u8_content_miss(self, mock_redis_service, mock_redis_client):
        """测试缓存未命中"""
        mock_redis_client.get.return_value = None
        
        import services.key_protect_service as key_protect_module
        
        with patch.object(key_protect_module, 'redis_service', mock_redis_service):
            result = await key_protect_module.get_cached_m3u8_content("video/test.m3u8")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_set_cached_m3u8_content(self, mock_redis_service, mock_redis_client):
        """测试设置缓存"""
        content = "#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI=\"enc.key\""
        mock_redis_client.setex.return_value = True
        
        import services.key_protect_service as key_protect_module
        
        with patch.object(key_protect_module, 'redis_service', mock_redis_service):
            result = await key_protect_module.set_cached_m3u8_content(
                path="video/test.m3u8",
                content=content,
                ttl=300
            )
            
            assert result is True
            mock_redis_client.setex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_redis_error(self, mock_redis_service, mock_redis_client):
        """测试 Redis 错误时的处理"""
        mock_redis_client.get.side_effect = Exception("Redis error")
        
        import services.key_protect_service as key_protect_module
        
        with patch.object(key_protect_module, 'redis_service', mock_redis_service):
            result = await key_protect_module.get_cached_m3u8_content("video/test.m3u8")
            
            # Redis 错误时返回 None，不影响正常流程
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
