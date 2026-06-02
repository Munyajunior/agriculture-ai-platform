# services/auth-service/app/core/redis_client.py
"""Redis client for caching and session management"""

import json
from typing import Optional, Any, Dict, List
from redis import asyncio as aioredis
import logging

from ..config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client wrapper"""
    
    def __init__(self):
        self.client: Optional[aioredis.Redis] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Redis connection"""
        try:
            self.client = await aioredis.from_url(
                settings.REDIS_URL,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                encoding="utf-8"
            )
            
            # Test connection
            await self.client.ping()
            self._initialized = True
            logger.info("Redis connection established")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def close(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            self._initialized = False
            logger.info("Redis connection closed")
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        if not self._initialized:
            return None
        return await self.client.get(key)
    
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set key-value pair"""
        if not self._initialized:
            return False
        
        if ttl:
            await self.client.setex(key, ttl, value)
        else:
            await self.client.set(key, value)
        return True
    
    async def setex(self, key: str, ttl: int, value: str) -> bool:
        """Set with expiration"""
        return await self.set(key, value, ttl)
    
    async def delete(self, *keys: str) -> int:
        """Delete keys"""
        if not self._initialized or not keys:
            return 0
        return await self.client.delete(*keys)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self._initialized:
            return False
        return bool(await self.client.exists(key))
    
    async def incr(self, key: str) -> int:
        """Increment counter"""
        if not self._initialized:
            return 0
        return await self.client.incr(key)
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on key"""
        if not self._initialized:
            return False
        return await self.client.expire(key, ttl)
    
    async def ttl(self, key: str) -> int:
        """Get TTL of key"""
        if not self._initialized:
            return -2
        return await self.client.ttl(key)
    
    async def ping(self) -> bool:
        """Check connection"""
        if not self._initialized:
            return False
        try:
            return bool(await self.client.ping())
        except:
            return False
    
    async def cache_get(self, key: str) -> Optional[Any]:
        """Get cached JSON data"""
        data = await self.get(key)
        if data:
            try:
                return json.loads(data)
            except:
                return data
        return None
    
    async def get_ttl(self, key: str) -> int:
        """Get TTL for a key in seconds"""
        if not self._initialized:
            return -2
        return await self.client.ttl(key)

    async def cache_set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set cached JSON data"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            elif not isinstance(value, str):
                value = str(value)
            return await self.set(key, value, ttl)
        except:
            return False


# Global Redis client instance
redis_client = RedisClient()