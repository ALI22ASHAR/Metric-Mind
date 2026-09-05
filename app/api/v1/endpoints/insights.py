import logging
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.anomalies import AnomalyReportResponse
from app.schemas.insights import DatasetInsightsSummary
from app.services.chat_service import ChatAnalystService
from app.services.insights_service import InsightsService
from app.api.v1.dependencies import require_dataset_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets/{dataset_id}", tags=["Insights & Anomalies"], dependencies=[Depends(require_dataset_access)])


@router.get(
    "/insights",
    response_model=DatasetInsightsSummary,
    status_code=status.HTTP_200_OK,
    summary="Get automated business insights & Pareto concentration",
    description="Computes 80/20 Pareto revenue concentration, top growth drivers, and margin risk analyses.",
)
async def get_dataset_insights(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
) -> DatasetInsightsSummary:
    """
    Fetch automated business insights for a dataset.
    """
    service = InsightsService(db)
    return await service.get_dataset_insights(dataset_id)


@router.get(
    "/anomalies",
    response_model=AnomalyReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Detect statistical anomalies & root cause drill-down",
    description="Identifies time-series outliers (spikes, drops) and decomposes dimensional contribution shifts.",
)
async def get_dataset_anomalies(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
) -> AnomalyReportResponse:
    """
    Detect statistical anomalies and root causes for a dataset.
    """
    service = InsightsService(db)
    return await service.get_dataset_anomalies(dataset_id)


@router.get(
    "/chat/sessions",
    status_code=status.HTTP_200_OK,
    summary="List chat sessions for dataset",
    description="Returns all conversation sessions for multi-turn thread persistence.",
)
async def list_chat_sessions(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    List chat sessions.
    """
    service = ChatAnalystService(db)
    sessions = await service.list_sessions(dataset_id)
    return [
        {
            "id": s.id,
            "dataset_id": s.dataset_id,
            "title": s.title,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
        }
        for s in sessions
    ]


@router.get(
    "/chat/sessions/{session_id}/messages",
    status_code=status.HTTP_200_OK,
    summary="Get chat history messages for session",
    description="Fetches chronological message history for a specific chat session.",
)
async def get_chat_session_messages(
    dataset_id: str,
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Get messages for a chat session.
    """
    service = ChatAnalystService(db)
    messages = await service.get_session_messages(session_id)
    return [
        {
            "id": m.id,
            "session_id": m.session_id,
            "role": m.role,
            "content": m.content,
            "sql_query": m.sql_query,
            "chart_type": m.chart_type,
            "created_at": m.created_at,
        }
        for m in messages
    ]
