# services/media-service/app/core/storage.py
"""Storage manager for R2/MinIO/S3 object storage"""

import io
import os
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, BinaryIO, Dict, Any, Tuple
from pathlib import Path
import asyncio
import mimetypes
import logging

from PIL import Image
import aiofiles
from botocore.exceptions import ClientError

from .config import settings

logger = logging.getLogger(__name__)


class StorageManager:
    """Unified storage manager supporting multiple backends"""
    
    def __init__(self):
        self.client = None
        self.bucket = settings.STORAGE_BUCKET
        self.storage_type = settings.STORAGE_TYPE
        self.public_url = settings.STORAGE_PUBLIC_URL
        
    async def initialize(self):
        """Initialize storage client"""
        if self.storage_type in ["minio", "s3", "r2"]:
            await self._init_s3_client()
        elif self.storage_type == "local":
            await self._init_local_storage()
        else:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")
        
        # Ensure bucket exists
        await self._ensure_bucket()
        logger.info(f"Storage initialized: {self.storage_type}")
    
    async def _init_s3_client(self):
        """Initialize S3-compatible client"""
        try:
            import aiobotocore.session
        except ImportError as exc:
            raise RuntimeError(
                "aiobotocore is required for minio/s3/r2 storage. "
                "Use STORAGE_TYPE=local or install a compatible aiobotocore/botocore pair."
            ) from exc

        session = aiobotocore.session.get_session()
        
        # Configure endpoint based on storage type
        endpoint = settings.STORAGE_ENDPOINT
        if self.storage_type == "r2":
            # Cloudflare R2 specific configuration
            endpoint = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
            access_key = settings.R2_ACCESS_KEY_ID
            secret_key = settings.R2_SECRET_ACCESS_KEY
        else:
            access_key = settings.STORAGE_ACCESS_KEY
            secret_key = settings.STORAGE_SECRET_KEY
        
        self.client = session.create_client(
            's3',
            endpoint_url=endpoint if settings.STORAGE_SECURE else f"http://{endpoint}",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=settings.STORAGE_REGION,
            use_ssl=settings.STORAGE_SECURE,
            config={
                'retries': {'max_attempts': 3},
                'connect_timeout': 10,
                'read_timeout': 30
            }
        )
    
    async def _init_local_storage(self):
        """Initialize local filesystem storage"""
        storage_path = Path(settings.LOCAL_STORAGE_PATH)
        storage_path.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (storage_path / "originals").mkdir(exist_ok=True)
        (storage_path / "thumbnails").mkdir(exist_ok=True)
        (storage_path / "processed").mkdir(exist_ok=True)
    
    async def _ensure_bucket(self):
        """Ensure storage bucket exists"""
        if self.storage_type in ["minio", "s3", "r2"]:
            try:
                await self.client.head_bucket(Bucket=self.bucket)
            except ClientError:
                # Bucket doesn't exist, create it
                await self.client.create_bucket(Bucket=self.bucket)
                logger.info(f"Created bucket: {self.bucket}")
                
                # Set bucket policy for public read (optional)
                if settings.STORAGE_PUBLIC_URL:
                    policy = {
                        "Version": "2012-10-17",
                        "Statement": [{
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": ["s3:GetObject"],
                            "Resource": f"arn:aws:s3:::{self.bucket}/*"
                        }]
                    }
                    await self.client.put_bucket_policy(
                        Bucket=self.bucket,
                        Policy=json.dumps(policy)
                    )
        elif self.storage_type == "local":
            # Local storage directory already created
            pass
    
    async def upload_file(
        self,
        file_data: bytes,
        file_path: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Upload file to storage"""
        
        if content_type is None:
            content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        
        if self.storage_type in ["minio", "s3", "r2"]:
            # Upload to S3-compatible storage
            extra_args = {
                'ContentType': content_type,
                'Metadata': metadata or {}
            }
            
            try:
                await self.client.put_object(
                    Bucket=self.bucket,
                    Key=file_path,
                    Body=file_data,
                    **extra_args
                )
                
                # Generate URL
                url = f"{self.public_url}/{self.bucket}/{file_path}" if self.public_url else None
                
                return {
                    "path": file_path,
                    "url": url,
                    "size": len(file_data),
                    "etag": hashlib.md5(file_data).hexdigest()
                }
            except Exception as e:
                logger.error(f"Failed to upload to S3: {e}")
                raise
        
        elif self.storage_type == "local":
            # Save to local filesystem
            storage_path = Path(settings.LOCAL_STORAGE_PATH)
            full_path = storage_path / file_path
            
            # Create directories if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            async with aiofiles.open(full_path, 'wb') as f:
                await f.write(file_data)
            
            # Generate URL
            url = f"/storage/{file_path}"  # Serve through nginx
            
            return {
                "path": str(full_path),
                "url": url,
                "size": len(file_data),
                "etag": hashlib.md5(file_data).hexdigest()
            }
    
    async def download_file(self, file_path: str) -> bytes:
        """Download file from storage"""
        
        if self.storage_type in ["minio", "s3", "r2"]:
            try:
                response = await self.client.get_object(
                    Bucket=self.bucket,
                    Key=file_path
                )
                data = await response['Body'].read()
                return data
            except Exception as e:
                logger.error(f"Failed to download from S3: {e}")
                raise
        
        elif self.storage_type == "local":
            storage_path = Path(settings.LOCAL_STORAGE_PATH)
            full_path = storage_path / file_path
            
            async with aiofiles.open(full_path, 'rb') as f:
                data = await f.read()
            return data
    
    async def delete_file(self, file_path: str):
        """Delete file from storage"""
        
        if self.storage_type in ["minio", "s3", "r2"]:
            try:
                await self.client.delete_object(
                    Bucket=self.bucket,
                    Key=file_path
                )
            except Exception as e:
                logger.error(f"Failed to delete from S3: {e}")
                raise
        
        elif self.storage_type == "local":
            storage_path = Path(settings.LOCAL_STORAGE_PATH)
            full_path = storage_path / file_path
            
            if full_path.exists():
                full_path.unlink()
    
    async def get_presigned_url(
        self,
        file_path: str,
        expires_in: int = 3600,
        method: str = 'get_object'
    ) -> str:
        """Generate presigned URL for temporary access"""
        
        if self.storage_type in ["minio", "s3", "r2"]:
            try:
                url = await self.client.generate_presigned_url(
                    ClientMethod=method,
                    Params={
                        'Bucket': self.bucket,
                        'Key': file_path
                    },
                    ExpiresIn=expires_in
                )
                return url
            except Exception as e:
                logger.error(f"Failed to generate presigned URL: {e}")
                raise
        else:
            # For local storage, return direct URL with expiration parameter
            # In production, implement signed URL mechanism
            return f"/storage/{file_path}?expires={datetime.utcnow().timestamp() + expires_in}"
    
    async def file_exists(self, file_path: str) -> bool:
        """Check if file exists in storage"""
        
        if self.storage_type in ["minio", "s3", "r2"]:
            try:
                await self.client.head_object(
                    Bucket=self.bucket,
                    Key=file_path
                )
                return True
            except ClientError:
                return False
        
        elif self.storage_type == "local":
            storage_path = Path(settings.LOCAL_STORAGE_PATH)
            full_path = storage_path / file_path
            return full_path.exists()
    
    async def list_files(
        self,
        prefix: str = "",
        max_keys: int = 1000
    ) -> list:
        """List files in storage"""
        
        if self.storage_type in ["minio", "s3", "r2"]:
            try:
                response = await self.client.list_objects_v2(
                    Bucket=self.bucket,
                    Prefix=prefix,
                    MaxKeys=max_keys
                )
                return response.get('Contents', [])
            except Exception as e:
                logger.error(f"Failed to list files: {e}")
                return []
        
        elif self.storage_type == "local":
            storage_path = Path(settings.LOCAL_STORAGE_PATH) / prefix
            if storage_path.exists():
                return [{"Key": str(f.relative_to(settings.LOCAL_STORAGE_PATH))} 
                        for f in storage_path.rglob("*") if f.is_file()]
            return []
    
    async def copy_file(self, source_path: str, dest_path: str):
        """Copy file within storage"""
        
        if self.storage_type in ["minio", "s3", "r2"]:
            try:
                copy_source = {'Bucket': self.bucket, 'Key': source_path}
                await self.client.copy_object(
                    Bucket=self.bucket,
                    Key=dest_path,
                    CopySource=copy_source
                )
            except Exception as e:
                logger.error(f"Failed to copy file: {e}")
                raise
        
        elif self.storage_type == "local":
            data = await self.download_file(source_path)
            await self.upload_file(data, dest_path)
    
    async def health_check(self) -> bool:
        """Check storage health"""
        try:
            if self.storage_type in ["minio", "s3", "r2"]:
                await self.client.list_buckets()
            elif self.storage_type == "local":
                Path(settings.LOCAL_STORAGE_PATH).exists()
            return True
        except Exception as e:
            logger.error(f"Storage health check failed: {e}")
            return False
    
    async def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """Get file metadata"""
        
        if self.storage_type in ["minio", "s3", "r2"]:
            try:
                response = await self.client.head_object(
                    Bucket=self.bucket,
                    Key=file_path
                )
                return {
                    "size": response['ContentLength'],
                    "content_type": response.get('ContentType', 'application/octet-stream'),
                    "last_modified": response['LastModified'],
                    "etag": response.get('ETag', ''),
                    "metadata": response.get('Metadata', {})
                }
            except Exception as e:
                logger.error(f"Failed to get metadata: {e}")
                return {}
        
        elif self.storage_type == "local":
            storage_path = Path(settings.LOCAL_STORAGE_PATH)
            full_path = storage_path / file_path
            if full_path.exists():
                stat = full_path.stat()
                return {
                    "size": stat.st_size,
                    "content_type": mimetypes.guess_type(full_path)[0],
                    "last_modified": datetime.fromtimestamp(stat.st_mtime),
                    "etag": hashlib.md5(full_path.read_bytes()).hexdigest()
                }
            return {}
