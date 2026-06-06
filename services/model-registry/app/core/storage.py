# services/model-registry/app/core/storage.py
"""Model artifact storage backends."""

from pathlib import Path

import aiofiles

from ..config import settings


class ModelStorage:
    """Minimal local model storage implementation."""

    def __init__(self) -> None:
        self.base_path = Path(settings.MODEL_CACHE_PATH)

    async def initialize(self) -> None:
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def upload_file(self, file_data: bytes, file_path: str) -> str:
        target = self.base_path / file_path
        target.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(target, "wb") as handle:
            await handle.write(file_data)
        return str(target)

    async def get_presigned_url(self, file_path: str, expires_in: int = 3600) -> str:
        return str(self.base_path / file_path)
