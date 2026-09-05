import logging
from typing import List, Optional, Tuple
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import storage_manager
from app.models.dataset import Dataset, DatasetStatus, generate_dataset_id
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.dataset import DatasetResponse, DatasetUploadResponse

logger = logging.getLogger(__name__)


class DatasetService:
    """
    Business logic layer for dataset upload, lifecycle management, and file storage.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = DatasetRepository(db)

    async def upload_dataset(self, file: UploadFile, workspace_id: Optional[str] = None) -> DatasetUploadResponse:
        """
        Validates, securely stores, and records metadata for an uploaded dataset.
        """
        dataset_id = generate_dataset_id()
        original_filename, ext = storage_manager.validate_file(file)

        logger.info("Initiating upload for dataset '%s' (ID: %s)", original_filename, dataset_id)

        # Stream and persist raw file to disk
        saved_file_path, file_size = await storage_manager.save_uploaded_file(dataset_id, file)

        # Detect MIME type
        content_type = file.content_type or (
            "text/csv" if ext == ".csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Automatically remove older versions of the same file to prevent past duplicate data accumulation
        try:
            existing_datasets, _ = await self.repository.list_all(skip=0, limit=100, workspace_id=workspace_id)
            for existing in existing_datasets:
                if existing.filename == original_filename:
                    logger.info("Pruning older version of '%s' (ID: %s)", original_filename, existing.id)
                    await self.delete_dataset(existing.id)
        except Exception as prune_err:
            logger.warning("Could not prune existing version of %s: %s", original_filename, prune_err)

        dataset = Dataset(
            id=dataset_id,
            workspace_id=workspace_id,
            filename=original_filename,
            file_path=saved_file_path,
            file_size_bytes=file_size,
            mime_type=content_type,
            status=DatasetStatus.UPLOADED.value,
        )

        try:
            created_dataset = await self.repository.create(dataset)
            logger.info("Successfully registered dataset '%s' (ID: %s)", original_filename, dataset_id)
            return DatasetUploadResponse(
                dataset_id=created_dataset.id,
                filename=created_dataset.filename,
                status=DatasetStatus(created_dataset.status),
                file_size_bytes=created_dataset.file_size_bytes,
                message="Dataset uploaded successfully.",
            )
        except Exception as exc:
            logger.error("Failed to save dataset metadata in database: %s", exc)
            # Cleanup orphaned file on disk
            storage_manager.delete_dataset_files(dataset_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error while registering uploaded dataset.",
            )

    async def get_dataset(self, dataset_id: str) -> DatasetResponse:
        """
        Fetch dataset metadata by ID, raising 404 if not found.
        """
        dataset = await self.repository.get_by_id(dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset with ID '{dataset_id}' was not found.",
            )
        return DatasetResponse.model_validate(dataset)

    async def list_datasets(
        self,
        skip: int = 0,
        limit: int = 50,
        workspace_id: Optional[str] = None,
    ) -> Tuple[List[DatasetResponse], int]:
        """
        List datasets with pagination.
        """
        datasets, total_count = await self.repository.list_all(skip=skip, limit=limit, workspace_id=workspace_id)
        items = [DatasetResponse.model_validate(ds) for ds in datasets]
        return items, total_count

    async def delete_dataset(self, dataset_id: str) -> None:
        """
        Deletes dataset metadata from database and cleans up disk files.
        """
        dataset = await self.repository.get_by_id(dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset with ID '{dataset_id}' was not found.",
            )

        # Delete database record
        await self.repository.delete(dataset_id)

        # Delete files from disk
        storage_manager.delete_dataset_files(dataset_id)
        logger.info("Deleted dataset and associated files for ID: %s", dataset_id)

    async def clear_past_datasets(
        self,
        keep_dataset_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> int:
        """
        Deletes all past datasets except the currently active one.
        """
        datasets, _ = await self.repository.list_all(skip=0, limit=200, workspace_id=workspace_id)
        deleted_count = 0
        for ds in datasets:
            if keep_dataset_id and ds.id == keep_dataset_id:
                continue
            try:
                await self.delete_dataset(ds.id)
                deleted_count += 1
            except Exception as exc:
                logger.warning("Failed to delete dataset %s during clear: %s", ds.id, exc)
        return deleted_count
