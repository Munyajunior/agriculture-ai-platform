# services/media-service/app/api/v1/upload.py
"""Upload endpoints for images"""

from typing import Optional
import io
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from uuid import UUID
import hashlib
from datetime import datetime, timedelta
from PIL import Image
from sqlalchemy import select

from ...core.storage import StorageManager
from ...core.image_processor import ImageProcessor
from ...core.cache import CacheManager
from ...database import get_db, MediaFile, UploadSession
from ...config import settings
from ...dependencies import verify_token, get_current_user_id
from ...workers.thumbnail_worker import thumbnail_worker, ThumbnailJob

router = APIRouter()
logger = logging.getLogger(__name__)
storage_manager = StorageManager()
image_processor = ImageProcessor()
cache_manager = CacheManager()
limiter = Limiter(key_func=get_remote_address)


@router.post("/image")
@limiter.limit(f"{settings.RATE_LIMIT_UPLOADS}/minute")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    user_id: UUID = Depends(get_current_user_id),
    farm_id: Optional[UUID] = None,
    generate_thumbnails: bool = True,
    db=Depends(get_db),
):
    """
    Upload a single image for plant disease detection
    """
    
    try:
        # Validate file type
        if file.content_type not in settings.ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type {file.content_type} not allowed. Allowed: {settings.ALLOWED_IMAGE_TYPES}"
            )
        
        # Read file
        file_data = await file.read()
        file_size = len(file_data)
        
        # Validate file size
        max_size = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Max size: {settings.MAX_IMAGE_SIZE_MB}MB"
            )
        
        # Generate unique filename
        file_hash = hashlib.md5(file_data).hexdigest()
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file_hash}_{file.filename.replace(' ', '_')}"
        
        # Process image. Thumbnails are generated asynchronously by the
        # background worker (see below), so skip inline thumbnail generation.
        processed = await image_processor.process_upload(
            file_data,
            safe_filename,
            generate_thumbnails=False
        )

        # Upload original to storage
        original_path = f"originals/{user_id}/{safe_filename}"
        upload_result = await storage_manager.upload_file(
            processed['optimized_data'],
            original_path,
            content_type=file.content_type,
            metadata={
                'user_id': str(user_id),
                'original_filename': file.filename,
                'farm_id': str(farm_id) if farm_id else ''
            }
        )

        # Save to database. Thumbnails are filled in by the worker; until then
        # thumbnail_paths is empty and is_processed reflects the pending state.
        media_file = MediaFile(
            user_id=user_id,
            filename=safe_filename,
            original_filename=file.filename,
            file_size=file_size,
            mime_type=file.content_type,
            storage_path=original_path,
            thumbnail_paths={},
            public_url=upload_result.get('url'),
            width=processed['width'],
            height=processed['height'],
            blurhash=processed['blurhash'],
            dominant_color=processed['dominant_color'],
            exif_data=processed['exif_data'],
            is_processed=not generate_thumbnails,
            processed_at=None if generate_thumbnails else datetime.utcnow(),
            metadata={
                'farm_id': str(farm_id) if farm_id else None,
                'compression_ratio': processed['compression_ratio'],
                'quality_score': processed['quality_analysis']['quality_score']
            }
        )

        db.add(media_file)
        await db.commit()
        await db.refresh(media_file)

        # Enqueue background thumbnail generation. The worker uploads the
        # thumbnails and updates MediaFile.thumbnail_paths when finished.
        if generate_thumbnails:
            thumbnail_worker.add_job(
                ThumbnailJob(
                    media_id=media_file.id,
                    image_data=processed['optimized_data'],
                    user_id=str(user_id),
                    filename=safe_filename,
                    created_at=datetime.utcnow(),
                )
            )
        
        # Cache the file metadata
        await cache_manager.set(
            f"media:{media_file.id}",
            {
                'id': str(media_file.id),
                'url': media_file.public_url,
                'width': media_file.width,
                'height': media_file.height,
                'blurhash': media_file.blurhash
            },
            ttl=settings.REDIS_CACHE_TTL
        )
        
        # Return response
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "id": str(media_file.id),
                "url": media_file.public_url,
                "thumbnails_pending": generate_thumbnails,
                "thumbnail_urls": {
                    size: f"/api/v1/download/thumbnail/{user_id}/{f'{size[0]}x{size[1]}'}/{safe_filename}"
                    for size in settings.THUMBNAIL_SIZES
                } if generate_thumbnails else {},
                "width": media_file.width,
                "height": media_file.height,
                "blurhash": media_file.blurhash,
                "quality_analysis": processed['quality_analysis'],
                "disease_regions": await image_processor.detect_disease_regions(
                    Image.open(io.BytesIO(processed['optimized_data']))
                ),
                "created_at": media_file.created_at.isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@router.post("/chunked/initiate")
async def initiate_chunked_upload(
    filename: str,
    total_size: int,
    content_type: str,
    user_id: UUID = Depends(get_current_user_id),
    db=Depends(get_db)
):
    """Initiate a chunked upload session for large files"""
    
    try:
        # Validate total size
        max_size = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
        if total_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Max size: {settings.MAX_IMAGE_SIZE_MB}MB"
            )
        
        # Generate upload ID
        upload_id = hashlib.md5(f"{user_id}{filename}{datetime.utcnow()}".encode()).hexdigest()
        
        # Calculate expires at (24 hours)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        # Create upload session
        session = UploadSession(
            user_id=user_id,
            upload_id=upload_id,
            filename=filename,
            total_size=total_size,
            expires_at=expires_at
        )
        
        db.add(session)
        await db.commit()
        
        # Calculate number of chunks (5MB each)
        chunk_size = 5 * 1024 * 1024  # 5MB
        total_chunks = (total_size + chunk_size - 1) // chunk_size
        
        return {
            "upload_id": upload_id,
            "chunk_size": chunk_size,
            "total_chunks": total_chunks,
            "expires_at": expires_at.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate upload: {str(e)}"
        )


@router.post("/chunked/upload")
async def upload_chunk(
    upload_id: str,
    chunk_number: int,
    file: UploadFile = File(...),
    user_id: UUID = Depends(get_current_user_id),
    db=Depends(get_db)
):
    """Upload a chunk of a file"""
    
    try:
        # Get upload session
        session = await db.execute(
            select(UploadSession).where(
                UploadSession.upload_id == upload_id,
                UploadSession.user_id == user_id,
                UploadSession.status == "in_progress"
            )
        )
        session = session.scalar_one_or_none()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upload session not found or expired"
            )
        
        # Check if chunk already uploaded
        if chunk_number in session.completed_chunks:
            return {"status": "already_uploaded", "chunk": chunk_number}
        
        # Read chunk data
        chunk_data = await file.read()
        
        # Store chunk (implementation depends on storage backend)
        chunk_path = f"temp/{upload_id}/chunk_{chunk_number}"
        await storage_manager.upload_file(chunk_data, chunk_path)
        
        # Update session
        session.completed_chunks.append(chunk_number)
        session.uploaded_size += len(chunk_data)
        session.updated_at = datetime.utcnow()
        
        await db.commit()
        
        # Check if all chunks uploaded
        total_chunks = (session.total_size + (5 * 1024 * 1024) - 1) // (5 * 1024 * 1024)
        is_complete = len(session.completed_chunks) == total_chunks
        
        return {
            "status": "completed" if is_complete else "uploaded",
            "chunk": chunk_number,
            "progress": (session.uploaded_size / session.total_size) * 100
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chunk upload failed: {str(e)}"
        )


@router.post("/chunked/complete")
async def complete_chunked_upload(
    upload_id: str,
    user_id: UUID = Depends(get_current_user_id),
    db=Depends(get_db)
):
    """Complete a chunked upload and assemble the file"""
    
    try:
        # Get upload session
        session = await db.execute(
            select(UploadSession).where(
                UploadSession.upload_id == upload_id,
                UploadSession.user_id == user_id
            )
        )
        session = session.scalar_one_or_none()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upload session not found"
            )
        
        # Assemble chunks (implementation depends on storage backend)
        total_chunks = (session.total_size + (5 * 1024 * 1024) - 1) // (5 * 1024 * 1024)
        
        # Download and assemble all chunks
        assembled_data = bytearray()
        for i in range(1, total_chunks + 1):
            chunk_path = f"temp/{upload_id}/chunk_{i}"
            chunk_data = await storage_manager.download_file(chunk_path)
            assembled_data.extend(chunk_data)
            
            # Clean up chunk
            await storage_manager.delete_file(chunk_path)
        
        # Process the assembled file as normal upload
        # ... (similar to single file upload)
        
        # Update session status
        session.status = "completed"
        session.updated_at = datetime.utcnow()
        await db.commit()
        
        # Clean up temp directory
        await storage_manager.delete_file(f"temp/{upload_id}")
        
        return {
            "status": "completed",
            "upload_id": upload_id,
            "filename": session.filename
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete upload: {str(e)}"
        )
