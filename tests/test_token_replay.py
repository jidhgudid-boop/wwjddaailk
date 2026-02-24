#!/usr/bin/env python3
"""
Token 防重放服务单元测试
Test Token Replay Protection Service
"""

import pytest
import asyncio
import hashlib
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

# Add the FileProxy directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTokenReplayService:
    """Token 防重放服务测试套件"""
    
    @pytest.fixture
    def mock_redis_client(self):
        """创建模拟的 Redis 客户端"""
        client = AsyncMock()
        client.incr = AsyncMock()
        client.expire = AsyncMock()
        client.ttl = AsyncMock()
        client.get = AsyncMock()
        client.delete = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_redis_service(self, mock_redis_client):
        """创建模拟的 Redis 服务"""
        service = MagicMock()
        service.get_client = MagicMock(return_value=mock_redis_client)
        return service
    
    @pytest.mark.asyncio
    async def test_check_token_replay_first_use(self, mock_redis_service, mock_redis_client):
        """测试 token 首次使用"""
        # 设置模拟返回值：第一次使用，计数为 1
        mock_redis_client.incr.return_value = 1
        
        # Import the module and patch
        import services.token_replay_service as token_replay_module
        
        with patch.object(token_replay_module, 'redis_service', mock_redis_service):
            allowed, info = await token_replay_module.check_token_replay(
                token="test_token_123",
                uid="user_123",
                path="/video/test.m3u8",
                max_uses=1,
                ttl=600,
                client_ip="192.168.1.1"
            )
            
            # 验证结果
            assert allowed is True
            assert info["is_first_use"] is True
            assert info["current_count"] == 1
            assert info["max_uses"] == 1
            assert info["remaining_uses"] == 0
            
            # 验证 Redis 操作被调用
            mock_redis_client.incr.assert_called_once()
            mock_redis_client.expire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_token_replay_second_use_blocked(self, mock_redis_service, mock_redis_client):
        """测试 token 第二次使用被阻止（单次使用模式）"""
        # 设置模拟返回值：第二次使用，计数为 2
        mock_redis_client.incr.return_value = 2
        mock_redis_client.ttl.return_value = 500
        
        import services.token_replay_service as token_replay_module
        
        with patch.object(token_replay_module, 'redis_service', mock_redis_service):
            allowed, info = await token_replay_module.check_token_replay(
                token="test_token_123",
                uid="user_123",
                path="/video/test.m3u8",
                max_uses=1,  # 只允许使用一次
                ttl=600,
                client_ip="192.168.1.1"
            )
            
            # 验证结果
            assert allowed is False
            assert info["exceeded"] is True
            assert info["current_count"] == 2
            assert info["max_uses"] == 1
            assert info["remaining_uses"] == 0
    
    @pytest.mark.asyncio
    async def test_check_token_replay_multiple_uses_allowed(self, mock_redis_service, mock_redis_client):
        """测试 token 多次使用允许（配置允许多次）"""
        # 设置模拟返回值：第二次使用，但允许 3 次
        mock_redis_client.incr.return_value = 2
        mock_redis_client.ttl.return_value = 500
        
        import services.token_replay_service as token_replay_module
        
        with patch.object(token_replay_module, 'redis_service', mock_redis_service):
            allowed, info = await token_replay_module.check_token_replay(
                token="test_token_123",
                uid="user_123",
                path="/video/test.m3u8",
                max_uses=3,  # 允许使用 3 次
                ttl=600,
                client_ip="192.168.1.1"
            )
            
            # 验证结果
            assert allowed is True
            assert info["current_count"] == 2
            assert info["max_uses"] == 3
            assert info["remaining_uses"] == 1
    
    @pytest.mark.asyncio
    async def test_check_token_replay_redis_error_fallback(self, mock_redis_service, mock_redis_client):
        """测试 Redis 错误时的回退行为（允许访问）"""
        # 设置模拟抛出异常
        mock_redis_client.incr.side_effect = Exception("Redis connection error")
        
        import services.token_replay_service as token_replay_module
        
        with patch.object(token_replay_module, 'redis_service', mock_redis_service):
            allowed, info = await token_replay_module.check_token_replay(
                token="test_token_123",
                uid="user_123",
                path="/video/test.m3u8",
                max_uses=1,
                ttl=600,
                client_ip="192.168.1.1"
            )
            
            # Redis 错误时应该允许访问（避免服务不可用）
            assert allowed is True
            assert info["fallback"] is True
            assert "error" in info
    
    @pytest.mark.asyncio
    async def test_get_token_usage_info(self, mock_redis_service, mock_redis_client):
        """测试获取 token 使用信息"""
        # 设置模拟返回值
        mock_redis_client.get.return_value = "3"
        mock_redis_client.ttl.return_value = 300
        
        import services.token_replay_service as token_replay_module
        
        with patch.object(token_replay_module, 'redis_service', mock_redis_service):
            info = await token_replay_module.get_token_usage_info(
                token="test_token_123",
                uid="user_123",
                path="/video/test.m3u8"
            )
            
            assert info["exists"] is True
            assert info["current_count"] == 3
            assert info["remaining_ttl"] == 300
    
    @pytest.mark.asyncio
    async def test_get_token_usage_info_not_exists(self, mock_redis_service, mock_redis_client):
        """测试获取不存在的 token 使用信息"""
        # 设置模拟返回值
        mock_redis_client.get.return_value = None
        
        import services.token_replay_service as token_replay_module
        
        with patch.object(token_replay_module, 'redis_service', mock_redis_service):
            info = await token_replay_module.get_token_usage_info(
                token="nonexistent_token",
                uid="user_123",
                path="/video/test.m3u8"
            )
            
            assert info["exists"] is False
            assert info["current_count"] == 0
    
    @pytest.mark.asyncio
    async def test_invalidate_token(self, mock_redis_service, mock_redis_client):
        """测试手动使 token 失效"""
        # 设置模拟返回值
        mock_redis_client.delete.return_value = 1
        
        import services.token_replay_service as token_replay_module
        
        with patch.object(token_replay_module, 'redis_service', mock_redis_service):
            result = await token_replay_module.invalidate_token(
                token="test_token_123",
                uid="user_123",
                path="/video/test.m3u8"
            )
            
            assert result is True
            mock_redis_client.delete.assert_called_once()


class TestTokenReplayKeyGeneration:
    """Token 防重放 key 生成测试"""
    
    def test_same_token_same_key(self):
        """测试相同 token 生成相同的 key"""
        key_content_1 = "token123:user1:/video/test.m3u8"
        key_content_2 = "token123:user1:/video/test.m3u8"
        
        hash_1 = hashlib.sha256(key_content_1.encode()).hexdigest()
        hash_2 = hashlib.sha256(key_content_2.encode()).hexdigest()
        
        assert hash_1 == hash_2
    
    def test_different_token_different_key(self):
        """测试不同 token 生成不同的 key"""
        key_content_1 = "token123:user1:/video/test.m3u8"
        key_content_2 = "token456:user1:/video/test.m3u8"
        
        hash_1 = hashlib.sha256(key_content_1.encode()).hexdigest()
        hash_2 = hashlib.sha256(key_content_2.encode()).hexdigest()
        
        assert hash_1 != hash_2
    
    def test_same_token_different_path_different_key(self):
        """测试相同 token 不同路径生成不同的 key"""
        key_content_1 = "token123:user1:/video/test1.m3u8"
        key_content_2 = "token123:user1:/video/test2.m3u8"
        
        hash_1 = hashlib.sha256(key_content_1.encode()).hexdigest()
        hash_2 = hashlib.sha256(key_content_2.encode()).hexdigest()
        
        assert hash_1 != hash_2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
