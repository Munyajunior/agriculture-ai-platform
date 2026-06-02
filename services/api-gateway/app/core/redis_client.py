# services/api-gateway/app/core/redis_client.py
"""Redis client for caching and rate limiting"""

import json
from typing import Optional, Any, Dict, List
import redis.asyncio as redis
from ..config import settings
import logging

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client wrapper"""
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Redis connection"""
        try:
            self.client = await redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                max_connections=20
            )
            await self.client.ping()
            self._initialized = True
            logger.info("Redis client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            raise
    
    async def close(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            self._initialized = False
            logger.info("Redis client closed")
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        if not self._initialized:
            return None
        return await self.client.get(key)
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: Optional[int] = None
    ) -> bool:
        """Set key-value pair with optional expiration"""
        if not self._initialized:
            return False
        
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        if expire:
            return await self.client.setex(key, expire, value)
        return await self.client.set(key, value)
    
    async def delete(self, *keys: str) -> int:
        """Delete one or more keys"""
        if not self._initialized:
            return 0
        return await self.client.delete(*keys)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self._initialized:
            return False
        return await self.client.exists(key) > 0
    
    async def increment(
        self, 
        key: str, 
        amount: int = 1, 
        expire: Optional[int] = None
    ) -> int:
        """Increment counter"""
        if not self._initialized:
            return 0
        
        value = await self.client.incrby(key, amount)
        if expire and value == amount:
            await self.client.expire(key, expire)
        
        return value
    
    async def get_json(self, key: str) -> Optional[Dict]:
        """Get JSON value"""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except:
                return None
        return None
    
    async def set_json(
        self, 
        key: str, 
        value: Dict, 
        expire: Optional[int] = None
    ) -> bool:
        """Set JSON value"""
        return await self.set(key, json.dumps(value), expire)
    
    async def sadd(self, key: str, *values: str) -> int:
        """Add to set"""
        if not self._initialized:
            return 0
        return await self.client.sadd(key, *values)
    
    async def srem(self, key: str, *values: str) -> int:
        """Remove from set"""
        if not self._initialized:
            return 0
        return await self.client.srem(key, *values)
    
    async def sismember(self, key: str, value: str) -> bool:
        """Check if value is in set"""
        if not self._initialized:
            return False
        return await self.client.sismember(key, value)
    
    async def smembers(self, key: str) -> List[str]:
        """Get all set members"""
        if not self._initialized:
            return []
        return await self.client.smembers(key)
    
    async def ping(self) -> bool:
        """Check Redis connectivity"""
        if not self._initialized:
            return False
        try:
            return await self.client.ping()
        except:
            return False
    
    async def clear_cache_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        if not self._initialized:
            return 0
        
        cursor = 0
        deleted = 0
        
        while True:
            cursor, keys = await self.client.scan(cursor, match=pattern, count=100)
            if keys:
                deleted += await self.client.delete(*keys)
            if cursor == 0:
                break
        
        return deleted


# Singleton instance
redis_client = RedisClient()