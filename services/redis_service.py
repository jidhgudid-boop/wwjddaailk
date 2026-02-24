"""
Redis 服务
管理 Redis 连接池和操作
"""
import redis.asyncio as redis_async
import logging
import weakref
from typing import List, Any, Tuple

logger = logging.getLogger(__name__)


class RedisService:
    """
    Redis 服务
    提供高性能的 Redis 连接池管理
    """
    
    def __init__(self):
        self.pool = None
        self._clients = weakref.WeakSet()
    
    async def initialize(self, config):
        """
        初始化 Redis 连接池
        
        Args:
            config: 配置对象
        """
        try:
            pool_kwargs = {
                'host': config.REDIS_HOST,
                'port': config.REDIS_PORT,
                'db': config.REDIS_DB,
                'password': config.REDIS_PASSWORD,
                'decode_responses': True,
                'max_connections': config.REDIS_POOL_SIZE,
                'retry_on_timeout': True,
                'retry_on_error': [ConnectionError, TimeoutError],
                'health_check_interval': 30
            }
            
            self.pool = redis_async.ConnectionPool(**pool_kwargs)
            
            # 测试连接
            redis_client = self.get_client()
            await redis_client.ping()
            logger.info(f"Redis 连接池初始化成功，连接数: {config.REDIS_POOL_SIZE}")
            
        except Exception as e:
            logger.error(f"Redis 连接池初始化失败: {str(e)}")
            raise
    
    def get_client(self):
        """
        获取 Redis 客户端实例
        
        Returns:
            redis_async.Redis: Redis 客户端
        """
        if self.pool is None:
            raise RuntimeError("Redis 连接池未初始化")
        client = redis_async.Redis(connection_pool=self.pool)
        self._clients.add(client)
        return client
    
    async def close(self):
        """关闭 Redis 连接池"""
        if self.pool:
            await self.pool.disconnect()
            logger.info("Redis 连接池已关闭")
    
    async def batch_operations(
        self,
        operations: List[Tuple],
        use_pipeline: bool = True
    ) -> List[Any]:
        """
        批量执行Redis操作
        
        Args:
            operations: 操作列表 [(op_type, key, *args), ...]
            use_pipeline: 是否使用pipeline
        
        Returns:
            List[Any]: 操作结果列表
        """
        redis_client = self.get_client()
        
        if not use_pipeline or len(operations) <= 1:
            # 单个操作或禁用pipeline
            results = []
            for op in operations:
                try:
                    result = await self._execute_operation(redis_client, op)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Redis操作失败: {op[0]} {op[1] if len(op) > 1 else ''} - {str(e)}")
                    results.append(None)
            return results
        
        # 使用pipeline批量执行
        try:
            pipe = redis_client.pipeline()
            for op in operations:
                self._add_operation_to_pipeline(pipe, op)
            
            return await pipe.execute()
        except Exception as e:
            logger.error(f"Redis pipeline操作失败: {str(e)}")
            # 回退到单个操作
            results = []
            for op in operations:
                try:
                    result = await self._execute_operation(redis_client, op)
                    results.append(result)
                except Exception as e2:
                    logger.error(f"Redis单个操作失败: {op[0]} - {str(e2)}")
                    results.append(None)
            return results
    
    async def _execute_operation(self, client, op: Tuple) -> Any:
        """执行单个Redis操作"""
        op_type, key, *args = op
        
        if op_type == 'get':
            return await client.get(key)
        elif op_type == 'set':
            if len(args) >= 2 and args[1] == 'EX':
                return await client.set(key, args[0], ex=args[2])
            elif len(args) >= 2 and args[1] == 'NX':
                return await client.set(key, args[0], nx=True)
            elif len(args) >= 4 and args[1] == 'EX' and args[3] == 'NX':
                return await client.set(key, args[0], ex=args[2], nx=True)
            else:
                return await client.set(key, args[0])
        elif op_type == 'expire':
            return await client.expire(key, args[0])
        elif op_type == 'ttl':
            return await client.ttl(key)
        elif op_type == 'incr':
            return await client.incr(key)
        elif op_type == 'keys':
            return await client.keys(key)
        elif op_type == 'delete':
            return await client.delete(key)
        else:
            return None
    
    def _add_operation_to_pipeline(self, pipe, op: Tuple):
        """将操作添加到pipeline"""
        op_type, key, *args = op
        
        if op_type == 'get':
            pipe.get(key)
        elif op_type == 'set':
            if len(args) >= 2 and args[1] == 'EX':
                pipe.set(key, args[0], ex=args[2])
            elif len(args) >= 2 and args[1] == 'NX':
                pipe.set(key, args[0], nx=True)
            elif len(args) >= 4 and args[1] == 'EX' and args[3] == 'NX':
                pipe.set(key, args[0], ex=args[2], nx=True)
            else:
                pipe.set(key, args[0])
        elif op_type == 'expire':
            pipe.expire(key, args[0])
        elif op_type == 'ttl':
            pipe.ttl(key)
        elif op_type == 'incr':
            pipe.incr(key)


# 全局Redis服务实例
redis_service = RedisService()
