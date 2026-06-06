# services/media-service/app/api/v1/download.py
"""Download endpoints for images"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from typing import Optional
from uuid import UUID
import io
from datetime import datetime
from sqlalchemy import select

from ...core.storage import StorageManager
from ...core.cache import CacheManager
from ...database import get_db, MediaFile
from ...dependencies import verify_token, get_current_user_id

router = APIRouter()
storage_manager = StorageManager()
cache_manager = CacheManager()


@router.get("/image/{media_id}")
async def download_image(
    media_id: UUID,
    size: Optional[str] = Query(None, description="Thumbnail size: 64x64, 256x256, 512x512"),
    presigned: bool = Query(False, description="Generate presigned URL instead of downloading"),
    user_id: UUID = Depends(get_current_user_id),
    db=Depends(get_db)
):
    """Download an image by ID"""
    
    try:
        # Check cache first
        cache_key = f"download:{media_id}:{size}"
        cached_url = await cache_manager.get(cache_key)
        
        if cached_url and presigned:
            return {"url": cached_url}
        
        # Get media record
        media = await db.execute(
            select(MediaFile).where(MediaFile.id == media_id)
        )
        media = media.scalar_one_or_none()
        
        if not media:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media not found"
            )
        
        # Check authorization (admin or owner)
        if media.user_id != user_id:
            # Check if user is admin (would need role check)
            # For now, only owner can access
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this media"
            )
        
        # Determine which file to serve
        if size and size in media.thumbnail_paths:
            file_path = media.thumbnail_paths[size]
            content_type = 'image/jpeg'
        else:
            file_path = media.storage_path
            content_type = media.mime_type
        
        # Generate presigned URL if requested
        if presigned:
            url = await storage_manager.get_presigned_url(file_path)
            await cache_manager.set(cache_key, url, ttl=300)  # Cache for 5 minutes
            return {"url": url}
        
        # Download file
        file_data = await storage_manager.download_file(file_path)
        
        # Return streaming response
        return StreamingResponse(
            io.BytesIO(file_data),
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{media.original_filename}"',
                "Cache-Control": "public, max-age=86400",  # Cache for 1 day
                "ETag": f'"{hash(file_data)}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Download failed: {str(e)}"
        )


@router.get("/thumbnail/{user_id}/{size}/{filename}")
async def get_thumbnail(
    user_id: UUID,
    size: str,
    filename: str,
    db=Depends(get_db)
):
    """Get a thumbnail image (public endpoint)"""
    
    try:
        # Validate size
        valid_sizes = ["64x64", "256x256", "512x512"]
        if size not in valid_sizes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid size. Must be one of: {valid_sizes}"
            )
        
        # Get media record
        media = await db.execute(
            select(MediaFile).where(
                MediaFile.user_id == user_id,
                MediaFile.filename == filename
            )
        )
        media = media.scalar_one_or_none()
        
        if not media:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media not found"
            )
        
        # Get thumbnail path
        if size not in media.thumbnail_paths:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Thumbnail size {size} not found"
            )
        
        file_path = media.thumbnail_paths[size]
        file_data = await storage_manager.download_file(file_path)
        
        return StreamingResponse(
            io.BytesIO(file_data),
            media_type='image/jpeg',
            headers={
                "Cache-Control": "public, max-age=31536000",  # Cache for 1 year
                "ETag": f'"{hash(file_data)}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get thumbnail: {str(e)}"
        )


@router.get("/batch")
async def batch_download(
    media_ids: list[UUID] = Query(...),
    user_id: UUID = Depends(get_current_user_id),
    db=Depends(get_db)
):
    """Download multiple images as a ZIP archive"""
    
    try:
        import zipfile
        from io import BytesIO
        
        # Create ZIP archive in memory
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for media_id in media_ids:
                # Get media record
                media = await db.execute(
                    select(MediaFile).where(MediaFile.id == media_id)
                )
                media = media.scalar_one_or_none()
                
                if not media or media.user_id != user_id:
                    continue
                
                # Download file
                file_data = await storage_manager.download_file(media.storage_path)
                
                # Add to ZIP
                zip_file.writestr(
                    f"{media.original_filename}",
                    file_data
                )
        
        zip_buffer.seek(0)
        
        return StreamingResponse(
            zip_buffer,
            media_type='application/zip',
            headers={
                "Content-Disposition": f'attachment; filename="images_{datetime.utcnow().strftime("%Y%m%d")}.zip"'
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch download failed: {str(e)}"
        )
