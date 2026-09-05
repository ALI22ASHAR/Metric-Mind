from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class InsightType(str, Enum):
    SUMMARY = "summary"
    CONCENTRATION = "concentration"
    GROWTH_DRIVER = "growth_driver"
    RISK = "risk"


class BusinessInsight(BaseModel):
    id: str = Field(..., description="Unique insight identifier")
    type: InsightType = Field(..., description="Category of insight")
    title: str = Field(..., description="Concise executive headline")
    description: str = Field(..., description="Detailed narrative explanation of the dynamic")
    metric: str = Field(..., description="Primary metric evaluated (e.g. 'total_revenue')")
    dimension: Optional[str] = Field(None, description="Primary dimension evaluated (e.g. 'Category')")
    impact_score: float = Field(..., ge=0.0, le=100.0, description="Priority / business impact score (0-100)")
    recommendation: Optional[str] = Field(None, description="Suggested strategic business action")

    model_config = ConfigDict(from_attributes=True)


class DatasetInsightsSummary(BaseModel):
    dataset_id: str
    total_insights: int
    insights: List[BusinessInsight]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
