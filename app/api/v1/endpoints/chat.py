import logging
from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.chat import (
    ChatQueryRequest,
    ChatQueryResponse,
    SuggestedQuestionsResponse,
)
from app.services.chat_service import ChatAnalystService
from app.api.v1.dependencies import require_dataset_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets/{dataset_id}/chat", tags=["AI Data Analyst"], dependencies=[Depends(require_dataset_access)])


@router.post(
    "",
    response_model=ChatQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a natural-language business question",
    description="Translates natural language to DuckDB SQL, executes against clean data with security guardrails, and synthesizes executive narrative answers.",
)
async def ask_chat_question(
    dataset_id: str,
    payload: ChatQueryRequest = Body(..., description="Natural-language business question and optional history"),
    db: AsyncSession = Depends(get_db),
) -> ChatQueryResponse:
    """
    Ask a natural-language data question.
    """
    service = ChatAnalystService(db)
    return await service.ask_question(dataset_id=dataset_id, request=payload)


@router.get(
    "/suggested-questions",
    response_model=SuggestedQuestionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get suggested analytical starter questions",
    description="Generates tailored business questions based on the dataset's available dimensions and computable metrics.",
)
async def get_suggested_questions(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
) -> SuggestedQuestionsResponse:
    """
    Get recommended questions for a dataset.
    """
    service = ChatAnalystService(db)
    return await service.get_suggested_questions(dataset_id=dataset_id)
