from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DatasetStatusEnum(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class DatasetUploadResponse(BaseModel):
    dataset_id: str = Field(..., description="Unique generated dataset identifier")
    filename: str = Field(..., description="Original filename of the uploaded dataset")
    status: DatasetStatusEnum = Field(..., description="Current status of the dataset")
    file_size_bytes: int = Field(..., description="Size of the uploaded file in bytes")
    message: str = Field("Dataset uploaded successfully.", description="Status message")

    model_config = ConfigDict(from_attributes=True)


class DatasetResponse(BaseModel):
    id: str = Field(..., description="Unique dataset identifier")
    filename: str = Field(..., description="Original filename")
    status: DatasetStatusEnum = Field(..., description="Current lifecycle status")
    file_size_bytes: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME content type")
    row_count: Optional[int] = Field(None, description="Total number of rows")
    column_count: Optional[int] = Field(None, description="Total number of columns")
    error_message: Optional[str] = Field(None, description="Diagnostic error details if failed")
    created_at: datetime = Field(..., description="Timestamp of upload creation")
    updated_at: datetime = Field(..., description="Timestamp of last update")

    model_config = ConfigDict(from_attributes=True)


class DatasetListResponse(BaseModel):
    items: List[DatasetResponse] = Field(..., description="List of datasets")
    total: int = Field(..., description="Total count of datasets")


class DatasetUpdate(BaseModel):
    status: Optional[DatasetStatusEnum] = None
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    error_message: Optional[str] = None
