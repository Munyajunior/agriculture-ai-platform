# services/media-service/app/workers/thumbnail_worker.py
"""Background worker for async thumbnail generation"""

import asyncio
from typing import Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging
from queue import Queue
from threading import Thread

from ..core.image_processor import ImageProcessor
from ..core.storage import StorageManager

logger = logging.getLogger(__name__)


@dataclass
class ThumbnailJob:
    """Thumbnail generation job"""
    media_id: str
    image_data: bytes
    user_id: str
    sizes: list
    created_at: datetime


class ThumbnailWorker:
    """Background worker for processing thumbnails"""
    
    def __init__(self, worker_count: int = 2):
        self.worker_count = worker_count
        self.queue = Queue()
        self.workers = []
        self.running = False
        self.image_processor = ImageProcessor()
        self.storage_manager = StorageManager()
        
    async def start(self):
        """Start background workers"""
        self.running = True
        
        # Initialize storage
        await self.storage_manager.initialize()
        
        # Create worker threads
        for i in range(self.worker_count):
            worker = Thread(target=self._worker_loop, name=f"thumbnail-worker-{i}")
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Started {self.worker_count} thumbnail workers")
    
    async def stop(self):
        """Stop background workers"""
        self.running = False
        
        # Wait for queue to empty
        while not self.queue.empty():
            await asyncio.sleep(1)
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=10)
        
        logger.info("Thumbnail workers stopped")
    
    def add_job(self, job: ThumbnailJob):
        """Add thumbnail job to queue"""
        self.queue.put(job)
        logger.debug(f"Added thumbnail job for media {job.media_id}")
    
    def _worker_loop(self):
        """Worker thread loop"""
        while self.running:
            try:
                # Get job from queue
                job = self.queue.get(timeout=1)
                
                # Process job
                asyncio.run(self._process_thumbnail_job(job))
                
                # Mark as done
                self.queue.task_done()
                
            except Exception as e:
                if self.running:
                    logger.error(f"Thumbnail worker error: {e}")
    
    async def _process_thumbnail_job(self, job: ThumbnailJob):
        """Process a thumbnail generation job"""
        try:
            # Generate thumbnails
            thumbnails = await self.image_processor._generate_thumbnails(
                Image.open(io.BytesIO(job.image_data))
            )
            
            # Upload thumbnails
            thumbnail_paths = {}
            for size, thumb_data in thumbnails.items():
                thumb_path = f"thumbnails/{job.user_id}/{size}/{job.media_id}.jpg"
                await self.storage_manager.upload_file(
                    thumb_data,
                    thumb_path,
                    content_type='image/jpeg'
                )
                thumbnail_paths[size] = thumb_path
            
            # Update database with thumbnail paths
            # This would need database access
            logger.info(f"Generated thumbnails for media {job.media_id}")
            
        except Exception as e:
            logger.error(f"Failed to generate thumbnails for {job.media_id}: {e}")


# Global worker instance
thumbnail_worker = ThumbnailWorker()