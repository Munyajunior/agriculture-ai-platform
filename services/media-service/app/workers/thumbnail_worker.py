# services/media-service/app/workers/thumbnail_worker.py
"""Background worker for async thumbnail generation"""

import asyncio
import io
from typing import Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging
from queue import Queue, Empty
from threading import Thread

from PIL import Image
from sqlalchemy import update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from ..core.image_processor import ImageProcessor
from ..core.storage import StorageManager
from ..config import settings
from ..database import MediaFile

logger = logging.getLogger(__name__)


# Dedicated engine for worker threads. Each job runs in its own event loop
# (via asyncio.run in a plain Thread), and asyncpg connections cannot be shared
# across event loops. NullPool ensures every session opens a fresh connection on
# the current loop and disposes it on exit — no connection is pooled across loops.
_worker_engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    poolclass=NullPool,
    echo=False,
)
_WorkerSession = async_sessionmaker(
    _worker_engine, class_=AsyncSession, expire_on_commit=False
)


@dataclass
class ThumbnailJob:
    """Thumbnail generation job"""
    media_id: str
    image_data: bytes
    user_id: str
    filename: str
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

        # Release the worker DB engine's connections
        await _worker_engine.dispose()

        logger.info("Thumbnail workers stopped")
    
    def add_job(self, job: ThumbnailJob):
        """Add thumbnail job to queue"""
        self.queue.put(job)
        logger.debug(f"Added thumbnail job for media {job.media_id}")
    
    def _worker_loop(self):
        """Worker thread loop"""
        while self.running:
            try:
                # Get job from queue (blocks up to 1s so we can re-check self.running)
                job = self.queue.get(timeout=1)
            except Empty:
                # No work available — normal idle state, keep polling
                continue

            try:
                # Process job
                asyncio.run(self._process_thumbnail_job(job))
            except Exception as e:
                if self.running:
                    logger.error(f"Thumbnail worker error: {e}")
            finally:
                # Mark as done
                self.queue.task_done()
    
    async def _process_thumbnail_job(self, job: ThumbnailJob):
        """Process a thumbnail generation job"""
        try:
            # Generate thumbnails
            thumbnails = await self.image_processor._generate_thumbnails(
                Image.open(io.BytesIO(job.image_data))
            )

            # Upload thumbnails. Path shape matches the download endpoints, which
            # resolve the real storage path from MediaFile.thumbnail_paths[size].
            thumbnail_paths = {}
            for size, thumb_data in thumbnails.items():
                thumb_path = f"thumbnails/{job.user_id}/{size}/{job.filename}"
                await self.storage_manager.upload_file(
                    thumb_data,
                    thumb_path,
                    content_type='image/jpeg'
                )
                thumbnail_paths[size] = thumb_path

            # Persist thumbnail paths and mark the record processed
            async with _WorkerSession() as session:
                await session.execute(
                    update(MediaFile)
                    .where(MediaFile.id == job.media_id)
                    .values(
                        thumbnail_paths=thumbnail_paths,
                        is_processed=True,
                        processing_error=None,
                        processed_at=datetime.utcnow(),
                    )
                )
                await session.commit()

            logger.info(
                f"Generated {len(thumbnail_paths)} thumbnails for media {job.media_id}"
            )

        except Exception as e:
            logger.error(f"Failed to generate thumbnails for {job.media_id}: {e}")
            # Record the failure on the media row so it isn't silently stuck pending
            try:
                async with _WorkerSession() as session:
                    await session.execute(
                        update(MediaFile)
                        .where(MediaFile.id == job.media_id)
                        .values(processing_error=str(e))
                    )
                    await session.commit()
            except Exception:
                logger.exception(
                    f"Could not record thumbnail error for media {job.media_id}"
                )


# Global worker instance
thumbnail_worker = ThumbnailWorker()