# services/media-service/app/core/cache.py
"""Cache management for media service"""

import json
import pickle
from typing import Any, Optional
import redis.asyncio as redis
import logging

from ..config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis cache manager for media metadata and temporary storage"""
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        
    async def initialize(self):
        """Initialize Redis connection"""
        try:
            self.client = await redis.from_url(
                settings.REDIS_URL,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # Test connection
            await self.client.ping()
            logger.info("Redis cache initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            # Fallback to dummy cache
            self.client = None
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.client:
            return None
        
        try:
            value = await self.client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.warning(f"Cache get failed for key {key}: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache"""
        if not self.client:
            return False
        
        try:
            serialized = json.dumps(value)
            await self.client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.client:
            return False
        
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete failed for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self.client:
            return False
        
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.warning(f"Cache exists check failed for key {key}: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment counter in cache"""
        if not self.client:
            return 0
        
        try:
            return await self.client.incrby(key, amount)
        except Exception as e:
            logger.warning(f"Cache increment failed for key {key}: {e}")
            return 0
    
    async def get_or_set(self, key: str, getter_func, ttl: int = 3600) -> Any:
        """Get from cache or execute getter and cache result"""
        value = await self.get(key)
        if value is not None:
            return value
        
        value = await getter_func()
        if value:
            await self.set(key, value, ttl)
        
        return value
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        if not self.client:
            return 0
        
        try:
            keys = await self.client.keys(pattern)
            if keys:
                return await self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache clear pattern failed for {pattern}: {e}")
            return 0
    
    async def health_check(self) -> bool:
        """Check cache health"""
        if not self.client:
            return False
        
        try:
            await self.client.ping()
            return True
        except Exception:
            return False
    
    async def close(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")