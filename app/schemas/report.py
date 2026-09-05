from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ReportSection(BaseModel):
    title: str
    content: str
    key_metrics: Optional[Dict[str, Any]] = None
    bullet_points: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)


class ExecutiveReportResponse(BaseModel):
    dataset_id: str
    title: str
    executive_summary: str
    domain: str
    quality_score: float
    sections: List[ReportSection]
    strategic_recommendations: List[str]
    markdown_content: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
