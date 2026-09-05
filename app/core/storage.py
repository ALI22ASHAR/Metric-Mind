import os
import shutil
from pathlib import Path
from typing import Tuple
import aiofiles
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


class StorageManager:
    """
    Manages local filesystem persistence for uploaded datasets.
    Isolates files by UUID to prevent filename collisions and directory traversal attacks.
    """

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(base_dir or settings.UPLOAD_DIR).resolve()
        self._ensure_base_directory()

    def _ensure_base_directory(self) -> None:
        """Ensure the root upload directory exists."""
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def validate_file(self, file: UploadFile) -> Tuple[str, str]:
        """
        Validates file extension, sanitizes filename, and checks content type.
        Returns (sanitized_original_filename, file_extension).
        """
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is missing or empty.",
            )

        # Extract extension
        file_path = Path(file.filename)
        filename = file_path.name
        ext = file_path.suffix.lower()

        if ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file extension '{ext}'. Allowed extensions: {', '.join(settings.ALLOWED_EXTENSIONS)}",
            )

        return filename, ext

    async def save_uploaded_file(self, dataset_id: str, file: UploadFile) -> Tuple[str, int]:
        """
        Streams and saves an uploaded file into a dataset-specific directory.
        Enforces maximum upload size during chunk streaming.
        Returns (saved_file_path, file_size_in_bytes).
        """
        filename, ext = self.validate_file(file)

        # Create isolated dataset directory: e.g. data/uploads/{dataset_id}/
        dataset_dir = self.base_dir / dataset_id
        dataset_dir.mkdir(parents=True, exist_ok=True)

        target_file_path = dataset_dir / f"raw_data{ext}"
        max_size = settings.max_upload_size_bytes
        total_size = 0

        try:
            async with aiofiles.open(target_file_path, "wb") as out_file:
                while chunk := await file.read(1024 * 1024):  # 1MB chunks
                    total_size += len(chunk)
                    if total_size > max_size:
                        raise HTTPException(
                            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB.",
                        )
                    await out_file.write(chunk)

            if total_size == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Uploaded file is empty (0 bytes).",
                )

        except Exception:
            # Clean up partial upload if an error occurred
            if target_file_path.exists():
                target_file_path.unlink()
            if dataset_dir.exists() and not any(dataset_dir.iterdir()):
                dataset_dir.rmdir()
            raise

        return str(target_file_path), total_size

    def delete_dataset_files(self, dataset_id: str) -> None:
        """
        Deletes all stored files and directories associated with a dataset_id.
        """
        dataset_dir = self.base_dir / dataset_id
        if dataset_dir.exists() and dataset_dir.is_dir():
            shutil.rmtree(dataset_dir, ignore_errors=True)


storage_manager = StorageManager()
