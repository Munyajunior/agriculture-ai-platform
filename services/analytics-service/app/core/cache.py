# services/analytics-service/app/core/cache.py
"""Redis caching utilities"""

import json
import pickle
from typing import Any, Optional, Callable
from functools import wraps
import redis.asyncio as redis
from app.config import settings

class RedisClient:
    """Redis client wrapper for caching"""
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
    
    async def initialize(self):
        """Initialize Redis connection"""
        self.client = await redis.from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD,
            decode_responses=False,
            encoding="utf-8"
        )
        
        # Test connection
        await self.client.ping()
    
    async def close(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.client:
            return None
        
        value = await self.client.get(key)
        if value:
            try:
                return pickle.loads(value)
            except:
                return value.decode('utf-8')
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600
    ) -> bool:
        """Set value in cache with TTL"""
        if not self.client:
            return False
        
        try:
            serialized = pickle.dumps(value)
            await self.client.setex(key, ttl, serialized)
            return True
        except:
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.client:
            return False
        
        result = await self.client.delete(key)
        return result > 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self.client:
            return False
        
        return await self.client.exists(key) > 0
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        if not self.client:
            return 0
        
        keys = await self.client.keys(pattern)
        if keys:
            return await self.client.delete(*keys)
        return 0
    
    async def ping(self) -> bool:
        """Check Redis connectivity"""
        if not self.client:
            return False
        
        try:
            return await self.client.ping()
        except:
            return False


# Global Redis client instance
redis_client = RedisClient()
cache_manager = redis_client


def cached(ttl: int = 3600, key_prefix: str = ""):
    """Decorator for caching function results"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix or func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached_result = await redis_client.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            await redis_client.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator
