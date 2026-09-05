import logging
from typing import Optional
from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.ai_dataset import AIDatasetUnderstanding
from app.schemas.dataset import (
    DatasetListResponse,
    DatasetResponse,
    DatasetStatusEnum,
    DatasetUploadResponse,
)
from app.schemas.profile import DatasetProfileResponse
from app.schemas.quality import CleaningPolicy, DataQualityReport
from app.schemas.semantic import SemanticMappingUpdate, SemanticModelSchema
from app.services.ai_dataset_service import AIDatasetService
from app.services.dataset_service import DatasetService
from app.services.profiler_service import ProfilerService
from app.services.quality_service import QualityService
from app.services.semantic_service import SemanticService
from app.api.v1.dependencies import get_workspace_id, require_dataset_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.post(
    "/upload",
    response_model=DatasetUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload, profile, normalize, and understand a dataset",
    description="Uploads a CSV or Excel business dataset, securely stores file, profiles distributions, creates clean Parquet representation, builds semantic model, and runs the AI dataset understanding agent.",
)
async def upload_dataset(
    file: UploadFile = File(..., description="CSV or Excel file to upload"),
    workspace_id: Optional[str] = Depends(get_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> DatasetUploadResponse:
    """
    Handles dataset file upload, stores raw file, and executes the full ingestion pipeline:
    Upload -> Profile -> Normalize (Parquet) -> Semantic Model -> AI Understanding.
    """
    dataset_service = DatasetService(db)
    upload_res = await dataset_service.upload_dataset(file, workspace_id=workspace_id)

    # 1. Automatically profile the dataset
    profiler_service = ProfilerService(db)
    try:
        await profiler_service.profile_dataset(upload_res.dataset_id)
        upload_res.status = DatasetStatusEnum.READY
        upload_res.message = "Dataset uploaded and processed successfully."
    except Exception as exc:
        logger.warning("Automatic profiling failed for %s: %s", upload_res.dataset_id, exc)

    # 2. Automatically generate clean analytical Parquet representation
    quality_service = QualityService(db)
    try:
        await quality_service.normalize_dataset(upload_res.dataset_id)
    except Exception as exc:
        logger.warning("Automatic normalization failed for %s: %s", upload_res.dataset_id, exc)

    # 3. Automatically construct initial semantic model
    semantic_service = SemanticService(db)
    try:
        await semantic_service.build_semantic_model(upload_res.dataset_id)
    except Exception as exc:
        logger.warning("Automatic semantic modeling failed for %s: %s", upload_res.dataset_id, exc)

    # 4. Automatically run AI Understanding agent
    ai_service = AIDatasetService(db)
    try:
        await ai_service.generate_understanding(upload_res.dataset_id)
    except Exception as exc:
        logger.warning("Automatic AI understanding failed for %s: %s", upload_res.dataset_id, exc)

    # 5. Automatically generate initial AI Dashboard
    from app.services.dashboard_service import DashboardService
    dashboard_service = DashboardService(db)
    try:
        await dashboard_service.generate_dashboard(upload_res.dataset_id)
    except Exception as exc:
        logger.warning("Automatic dashboard generation failed for %s: %s", upload_res.dataset_id, exc)

    return upload_res


@router.get(
    "",
    response_model=DatasetListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all uploaded datasets",
    description="Returns a paginated list of all uploaded datasets ordered by creation time descending.",
)
async def list_datasets(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Max items per page"),
    db: AsyncSession = Depends(get_db),
    workspace_id: Optional[str] = Depends(get_workspace_id),
) -> DatasetListResponse:
    """
    List datasets with pagination.
    """
    service = DatasetService(db)
    items, total = await service.list_datasets(skip=skip, limit=limit, workspace_id=workspace_id)
    return DatasetListResponse(items=items, total=total)


@router.get(
    "/{dataset_id}",
    response_model=DatasetResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dataset details",
    description="Retrieves metadata and processing status for a specific dataset ID.",
)
async def get_dataset(
    dataset_id: str,
    _: None = Depends(require_dataset_access),
    db: AsyncSession = Depends(get_db),
) -> DatasetResponse:
    """
    Fetch a single dataset by ID.
    """
    service = DatasetService(db)
    return await service.get_dataset(dataset_id)


@router.get(
    "/{dataset_id}/profile",
    response_model=DatasetProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dataset statistical profile & data quality report",
    description="Returns comprehensive column profiling, statistical distributions, cardinality, and data quality warnings.",
)
async def get_dataset_profile(
    dataset_id: str,
    _: None = Depends(require_dataset_access),
    db: AsyncSession = Depends(get_db),
) -> DatasetProfileResponse:
    """
    Fetch or generate data profiling results for a dataset.
    """
    profiler_service = ProfilerService(db)
    return await profiler_service.get_dataset_profile(dataset_id)


@router.post(
    "/{dataset_id}/profile",
    response_model=DatasetProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger dataset re-profiling",
    description="Forces a recalculation of the statistical profile and data quality checks.",
)
async def re_profile_dataset(
    dataset_id: str,
    _: None = Depends(require_dataset_access),
    db: AsyncSession = Depends(get_db),
) -> DatasetProfileResponse:
    """
    Re-runs profiling on the dataset.
    """
    profiler_service = ProfilerService(db)
    return await profiler_service.profile_dataset(dataset_id)


@router.get(
    "/{dataset_id}/quality-report",
    response_model=DataQualityReport,
    status_code=status.HTTP_200_OK,
    summary="Get dataset quality score and assessment report",
    description="Returns overall quality score (0-100), issue breakdown, outlier detections, and audit log of cleaning actions.",
)
async def get_quality_report(
    dataset_id: str,
    _: None = Depends(require_dataset_access),
    db: AsyncSession = Depends(get_db),
) -> DataQualityReport:
    """
    Fetch data quality report and health score for a dataset.
    """
    quality_service = QualityService(db)
    return await quality_service.get_quality_report(dataset_id)


@router.post(
    "/{dataset_id}/normalize",
    response_model=DataQualityReport,
    status_code=status.HTTP_200_OK,
    summary="Execute normalization with custom cleaning policy",
    description="Applies custom data hygiene rules, generates updated clean Parquet representation, and returns new quality report.",
)
async def normalize_dataset(
    dataset_id: str,
    policy: Optional[CleaningPolicy] = Body(default=None, description="Custom cleaning policy"),
    _: None = Depends(require_dataset_access),
    db: AsyncSession = Depends(get_db),
) -> DataQualityReport:
    """
    Re-normalizes dataset with specified cleaning policy.
    """
    quality_service = QualityService(db)
    return await quality_service.normalize_dataset(dataset_id, policy)


@router.get(
    "/{dataset_id}/semantic-model",
    response_model=SemanticModelSchema,
    status_code=status.HTTP_200_OK,
    summary="Get dataset semantic model and concept mappings",
    description="Returns mappings of columns to standard business concepts (quantity, sale price, cost, product, date), dimensions, and measures.",
)
async def get_semantic_model(
    dataset_id: str,
    _: None = Depends(require_dataset_access),
    db: AsyncSession = Depends(get_db),
) -> SemanticModelSchema:
    """
    Retrieves the semantic model for a dataset.
    """
    service = SemanticService(db)
    return await service.get_semantic_model(dataset_id)


@router.put(
    "/{dataset_id}/semantic-model",
    response_model=SemanticModelSchema,
    status_code=status.HTTP_200_OK,
    summary="Update dataset semantic model mappings",
    description="Applies concept mapping overrides while strictly validating that all mapped columns exist in the dataset.",
)
async def update_semantic_model(
    dataset_id: str,
    update_data: SemanticMappingUpdate = Body(..., description="Mapping overrides"),
    _: None = Depends(require_dataset_access),
    db: AsyncSession = Depends(get_db),
) -> SemanticModelSchema:
    """
    Updates semantic model mappings.
    """
    service = SemanticService(db)
    return await service.update_semantic_model(dataset_id, update_data)


@router.get(
    "/{dataset_id}/ai-understanding",
    response_model=AIDatasetUnderstanding,
    status_code=status.HTTP_200_OK,
    summary="Get AI dataset understanding and executive synthesis",
    description="Retrieves the structured business synthesis, recommended metrics, questions, and dimensional hierarchies generated by the AI agent.",
)
async def get_ai_understanding(
    dataset_id: str,
    _: None = Depends(require_dataset_access),
    db: AsyncSession = Depends(get_db),
) -> AIDatasetUnderstanding:
    """
    Retrieves cached AI understanding or generates it on demand.
    """
    service = AIDatasetService(db)
    return await service.get_understanding(dataset_id)


@router.post(
    "/{dataset_id}/ai-understanding",
    response_model=AIDatasetUnderstanding,
    status_code=status.HTTP_200_OK,
    summary="Trigger AI dataset understanding analysis",
    description="Forces the AI agent to re-analyze column distributions, hierarchies, and business questions.",
)
async def trigger_ai_understanding(
    dataset_id: str,
    _: None = Depends(require_dataset_access),
    db: AsyncSession = Depends(get_db),
) -> AIDatasetUnderstanding:
    """
    Executes AI understanding agent for the dataset.
    """
    service = AIDatasetService(db)
    return await service.generate_understanding(dataset_id)


@router.post(
    "/clear-past",
    status_code=status.HTTP_200_OK,
    summary="Clear past datasets",
    description="Deletes all historical/past datasets except the specified active dataset.",
)
async def clear_past_datasets_endpoint(
    keep_dataset_id: Optional[str] = Query(None, description="Dataset ID to keep active"),
    workspace_id: Optional[str] = Depends(get_workspace_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Cleans up all past datasets except the current one.
    """
    service = DatasetService(db)
    count = await service.clear_past_datasets(keep_dataset_id=keep_dataset_id, workspace_id=workspace_id)
    return {
        "deleted_count": count,
        "message": f"Successfully cleared {count} past dataset(s).",
    }


@router.delete(
    "/{dataset_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a dataset",
    description="Deletes dataset record from database, associated profiles, quality reports, semantic models, AI understandings, and removes all stored files from disk.",
)
async def delete_dataset(
    dataset_id: str,
    _: None = Depends(require_dataset_access),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Deletes dataset and its stored files.
    """
    service = DatasetService(db)
    await service.delete_dataset(dataset_id)
    return {
        "dataset_id": dataset_id,
        "deleted": True,
        "message": f"Dataset '{dataset_id}' and all associated files have been permanently deleted.",
    }

