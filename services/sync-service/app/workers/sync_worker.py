# services/sync-service/app/workers/sync_worker.py
"""Background worker for processing sync queue"""

import asyncio
from typing import List
from datetime import datetime
import logging

from ..core.sync_engine import SyncEngine
from ..database import AsyncSessionLocal, SyncQueue, SyncStatus
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)


class SyncWorker:
    """Background worker that processes pending sync items"""
    
    def __init__(self, worker_count: int = 4, poll_interval: int = 30):
        self.worker_count = worker_count
        self.poll_interval = poll_interval
        self.running = False
        self.workers = []
        self.sync_engine = SyncEngine()
        
    async def start(self):
        """Start sync workers"""
        self.running = True
        
        for i in range(self.worker_count):
            worker = asyncio.create_task(self._worker_loop(i))
            self.workers.append(worker)
        
        logger.info(f"Started {self.worker_count} sync workers")
    
    async def stop(self):
        """Stop sync workers"""
        self.running = False
        
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        logger.info("Sync workers stopped")
    
    async def _worker_loop(self, worker_id: int):
        """Worker loop for processing sync items"""
        
        while self.running:
            try:
                # Get pending items grouped by device
                items_by_device = await self._get_pending_items_grouped()
                
                for device_id, items in items_by_device.items():
                    await self._process_device_items(device_id, items)
                
                # Wait before next poll
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(5)
    
    async def _get_pending_items_grouped(self) -> dict:
        """Get pending items grouped by device"""
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SyncQueue)
                .where(
                    and_(
                        SyncQueue.sync_status == SyncStatus.PENDING,
                        SyncQueue.retry_count < SyncQueue.max_retries
                    )
                )
                .order_by(SyncQueue.created_at)
                .limit(1000)
            )
            
            items = result.scalars().all()
            
            # Group by device
            grouped = {}
            for item in items:
                if item.device_id not in grouped:
                    grouped[item.device_id] = []
                grouped[item.device_id].append(item)
            
            return grouped
    
    async def _process_device_items(self, device_id: str, items: List):
        """Process all pending items for a device"""
        
        try:
            # Get user_id from first item
            user_id = items[0].user_id
            
            # Prepare changes
            changes = []
            for item in items:
                changes.append({
                    "entity_type": item.entity_type.value,
                    "entity_id": item.entity_id,
                    "operation": "update",
                    "data": item.entity_data,
                    "version": item.version
                })
            
            # Sync device
            result = await self.sync_engine.sync_device(
                device_id,
                user_id,
                None,
                changes
            )
            
            # Mark successful items as synced
            if result['synced_items']:
                await self.sync_engine.mark_synced(result['synced_items'])
            
            # Mark failed items for retry
            if result['failed_items']:
                await self.sync_engine.mark_failed(
                    result['failed_items'],
                    "Sync failed",
                    retry=True
                )
                
        except Exception as e:
            logger.error(f"Failed to process items for device {device_id}: {e}")
            
            # Mark all items for retry
            item_ids = [str(item.id) for item in items]
            await self.sync_engine.mark_failed(
                item_ids,
                str(e),
                retry=True
            )


# Global worker instance
sync_worker = SyncWorker()