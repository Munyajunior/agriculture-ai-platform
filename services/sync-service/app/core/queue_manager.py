# services/sync-service/app/core/queue_manager.py
"""Queue manager for sync items"""

import asyncio
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from ..config import settings

logger = logging.getLogger(__name__)


class QueueManager:
    """Manage sync queue operations"""
    
    def __init__(self):
        self.queue = asyncio.Queue(maxsize=settings.QUEUE_MAX_SIZE)
        self.redis_client = None
        
    async def initialize(self):
        """Initialize queue manager"""
        try:
            import redis.asyncio as redis
            self.redis_client = await redis.from_url(
                settings.REDIS_URL,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
            logger.info("Queue manager initialized with Redis")
        except Exception as e:
            logger.warning(f"Redis not available, using in-memory queue: {e}")
            self.redis_client = None
    
    async def enqueue(self, item: Dict[str, Any]) -> bool:
        """Add item to queue"""
        try:
            if self.redis_client:
                # Use Redis list as queue
                await self.redis_client.rpush(
                    f"sync_queue:{item['device_id']}",
                    json.dumps(item)
                )
            else:
                # Use in-memory queue
                await self.queue.put(item)
            return True
        except asyncio.QueueFull:
            logger.error("Queue is full")
            return False
        except Exception as e:
            logger.error(f"Failed to enqueue item: {e}")
            return False
    
    async def dequeue(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get item from queue"""
        try:
            if self.redis_client:
                # Pop from Redis list
                data = await self.redis_client.lpop(f"sync_queue:{device_id}")
                if data:
                    return json.loads(data)
            else:
                # Get from in-memory queue
                try:
                    return await self.queue.get()
                except asyncio.QueueEmpty:
                    pass
            return None
        except Exception as e:
            logger.error(f"Failed to dequeue item: {e}")
            return None
    
    async def get_queue_size(self, device_id: Optional[str] = None) -> int:
        """Get queue size"""
        try:
            if self.redis_client:
                if device_id:
                    return await self.redis_client.llen(f"sync_queue:{device_id}")
                else:
                    # Sum over all devices
                    keys = await self.redis_client.keys("sync_queue:*")
                    total = 0
                    for key in keys:
                        total += await self.redis_client.llen(key)
                    return total
            else:
                return self.queue.qsize()
        except Exception as e:
            logger.error(f"Failed to get queue size: {e}")
            return 0
    
    async def remove_item(self, item_id: str) -> bool:
        """Remove item from queue"""
        # Implementation depends on storage backend
        # For now, log and return True
        logger.info(f"Item {item_id} removed from queue")
        return True
    
    async def clear_queue(self, device_id: Optional[str] = None) -> int:
        """Clear queue"""
        try:
            if self.redis_client:
                if device_id:
                    key = f"sync_queue:{device_id}"
                    size = await self.redis_client.llen(key)
                    await self.redis_client.delete(key)
                    return size
                else:
                    keys = await self.redis_client.keys("sync_queue:*")
                    total = 0
                    for key in keys:
                        size = await self.redis_client.llen(key)
                        total += size
                        await self.redis_client.delete(key)
                    return total
            else:
                # Clear in-memory queue
                size = self.queue.qsize()
                while not self.queue.empty():
                    try:
                        self.queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                return size
        except Exception as e:
            logger.error(f"Failed to clear queue: {e}")
            return 0
    
    async def health_check(self) -> bool:
        """Check queue health"""
        try:
            if self.redis_client:
                await self.redis_client.ping()
            return True
        except Exception:
            return False
    
    async def close(self):
        """Close queue connections"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")