from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


@dataclass
class UploadResult:
    key: str
    uri: str
    size: int


class BaseStorage:
    async def upload(self, key: str, data: bytes, content_type: str) -> UploadResult:
        raise NotImplementedError

    async def get_url(self, key: str, expires: int = 3600) -> str:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError

    async def health_check(self) -> bool:
        raise NotImplementedError


class LocalStorage(BaseStorage):
    def __init__(self, base_dir: str = "/tmp/esg-uploads"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def upload(self, key: str, data: bytes, content_type: str) -> UploadResult:
        path = self.base_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return UploadResult(key=key, uri=f"file://{path}", size=len(data))

    async def get_url(self, key: str, expires: int = 3600) -> str:
        return f"file://{self.base_dir / key}"

    async def delete(self, key: str) -> None:
        path = self.base_dir / key
        if path.exists():
            path.unlink()

    async def health_check(self) -> bool:
        return self.base_dir.exists() and os.access(self.base_dir, os.W_OK)


class MinIOStorage(BaseStorage):
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ):
        from miniopy_async import Minio

        self.client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self.bucket = bucket

    async def _ensure_bucket(self) -> None:
        exists = await self.client.bucket_exists(self.bucket)
        if not exists:
            await self.client.make_bucket(self.bucket)

    async def upload(self, key: str, data: bytes, content_type: str) -> UploadResult:
        from io import BytesIO

        await self._ensure_bucket()
        stream = BytesIO(data)
        await self.client.put_object(
            self.bucket, key, stream, length=len(data), content_type=content_type
        )
        return UploadResult(key=key, uri=f"s3://{self.bucket}/{key}", size=len(data))

    async def get_url(self, key: str, expires: int = 3600) -> str:
        from datetime import timedelta

        return await self.client.presigned_get_object(self.bucket, key, expires=timedelta(seconds=expires))

    async def delete(self, key: str) -> None:
        await self.client.remove_object(self.bucket, key)

    async def health_check(self) -> bool:
        try:
            await self.client.bucket_exists(self.bucket)
            return True
        except Exception:
            return False


def generate_storage_key(org_id: int, filename: str) -> str:
    safe_name = filename.replace("/", "_").replace("\\", "_")
    return f"{org_id}/{uuid.uuid4().hex}_{safe_name}"


_storage_instance: BaseStorage | None = None


def get_storage() -> BaseStorage:
    global _storage_instance
    if _storage_instance is not None:
        return _storage_instance

    backend = (settings.storage_backend or "local").lower()
    if backend == "minio" or backend == "s3":
        _storage_instance = MinIOStorage(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            secure=settings.minio_secure,
        )
    else:
        _storage_instance = LocalStorage()
    return _storage_instance
