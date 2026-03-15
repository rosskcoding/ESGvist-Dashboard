"""
Storage abstraction layer.

Provides unified interface for local and cloud storage.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

from app.config import settings


class StorageError(Exception):
    """Storage operation failed."""
    pass


class StorageBackend(ABC):
    """Abstract storage backend."""

    @abstractmethod
    async def exists(self, storage_path: str) -> bool:
        """Check if file exists at storage path."""
        pass

    @abstractmethod
    async def read(self, storage_path: str) -> bytes:
        """Read file contents."""
        pass

    @abstractmethod
    async def write(self, storage_path: str, content: bytes) -> None:
        """Write file contents."""
        pass

    @abstractmethod
    async def delete(self, storage_path: str) -> None:
        """Delete file."""
        pass

    @abstractmethod
    async def download(self, storage_path: str, local_path: Path) -> None:
        """Download file to local path."""
        pass

    @abstractmethod
    async def upload(self, storage_path: str, content: bytes | Path) -> None:
        """Upload file from bytes or local path."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        # Ensure base path exists
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _full_path(self, storage_path: str) -> Path:
        """Get full filesystem path."""
        return self.base_path / storage_path

    async def exists(self, storage_path: str) -> bool:
        """Check if file exists."""
        return self._full_path(storage_path).exists()

    async def read(self, storage_path: str) -> bytes:
        """Read file contents."""
        full_path = self._full_path(storage_path)
        if not full_path.exists():
            raise StorageError(f"File not found: {storage_path}")
        return full_path.read_bytes()

    async def write(self, storage_path: str, content: bytes) -> None:
        """Write file contents."""
        full_path = self._full_path(storage_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)

    async def delete(self, storage_path: str) -> None:
        """Delete file."""
        full_path = self._full_path(storage_path)
        if full_path.exists():
            full_path.unlink()

    async def download(self, storage_path: str, local_path: Path) -> None:
        """
        Download file to local path.

        For local storage, this is just a copy operation.
        """
        content = await self.read(storage_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(content)

    async def upload(self, storage_path: str, content: bytes | Path) -> None:
        """
        Upload file from bytes or local path.

        Args:
            storage_path: Target storage path
            content: Either bytes or Path to local file
        """
        if isinstance(content, Path):
            content = content.read_bytes()

        await self.write(storage_path, content)


# Singleton instances
_storage_backend: StorageBackend | None = None
_builds_storage_backend: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    """
    Get assets storage backend instance (singleton).

    Returns:
        Configured storage backend based on settings.storage_type

    Example:
        >>> storage = get_storage_backend()
        >>> await storage.write("company/abc/file.txt", b"content")
    """
    global _storage_backend

    if _storage_backend is not None:
        return _storage_backend

    if settings.storage_type == "local":
        _storage_backend = LocalStorageBackend(settings.storage_local_path)
    else:
        raise NotImplementedError(f"Storage type '{settings.storage_type}' not implemented")

    return _storage_backend


def get_builds_storage() -> StorageBackend:
    """
    Get builds/artifacts storage backend instance (singleton).

    Separate from assets storage to allow different backends:
    - Assets: persistent user uploads (images, documents)
    - Builds: temporary exports with TTL/cleanup policy

    Returns:
        Configured storage backend based on settings.builds_storage_type

    Example:
        >>> storage = get_builds_storage()
        >>> await storage.write("build-abc123.zip", zip_content)
    """
    global _builds_storage_backend

    if _builds_storage_backend is not None:
        return _builds_storage_backend

    if settings.builds_storage_type == "local":
        _builds_storage_backend = LocalStorageBackend(settings.builds_local_path)
    elif settings.builds_storage_type == "s3":
        from app.services.storage_s3 import S3StorageBackend
        _builds_storage_backend = S3StorageBackend(
            bucket=settings.builds_s3_bucket,
            region=settings.storage_s3_region,
            prefix="builds",
        )
    else:
        raise NotImplementedError(f"Builds storage type '{settings.builds_storage_type}' not implemented")

    return _builds_storage_backend

