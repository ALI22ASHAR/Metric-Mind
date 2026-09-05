from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.analytics import DimensionFilter


class TimeSeriesGranularity(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class ConfidenceFactor(BaseModel):
    """
    A single contributing factor to the overall data-quality confidence score.
    """
    label: str = Field(..., description="Human-readable factor name")
    score: float = Field(..., ge=0, le=100, description="Per-factor score (0-100)")
    detail: Optional[str] = Field(None, description="Why this factor scored the way it did")


class PeriodOverPeriodGrowth(BaseModel):
    """
    Calculated growth comparisons between the most recent period and its predecessor (e.g. MoM, QoQ, YoY).
    """
    metric_id: str
    current_period: str
    prior_period: str
    current_value: float
    prior_value: float
    absolute_change: float
    growth_percentage: Optional[float] = None
    trend: str = "flat"  # "up", "down", "flat"
    # New: data quality + headline context for executive cards
    data_quality_score: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Overall 0-100 confidence in the metric, derived from null %, row count, and quality warnings.",
    )
    confidence_label: Optional[str] = Field(
        None,
        description="Human-readable label, e.g. 'High confidence', 'Limited history'.",
    )
    confidence_factors: List[ConfidenceFactor] = Field(
        default_factory=list,
        description="Per-factor breakdown of the data quality score.",
    )
    headline_insight: Optional[str] = Field(
        None,
        description="One-sentence narrative of what drove the change, e.g. 'Driven by +12% in Engineering'.",
    )


class TimeSeriesPoint(BaseModel):
    """
    Single discrete time bucket observation.
    """
    period_start: str
    period_label: str
    values: Dict[str, Optional[float]]
    formatted_values: Dict[str, str] = Field(default_factory=dict)


class TimeSeriesRequest(BaseModel):
    """
    Request payload to aggregate metrics across a temporal dimension.
    """
    granularity: Optional[TimeSeriesGranularity] = Field(
        None,
        description="Time aggregation interval (day, week, month, quarter, year). Auto-selected if omitted.",
    )
    metrics: List[str] = Field(default_factory=lambda: ["total_revenue"], description="Metric IDs to calculate")
    filters: Optional[List[DimensionFilter]] = Field(default=None, description="Optional dimension filters")


class TimeSeriesResponse(BaseModel):
    """
    Response containing chronologically ordered time series points and growth rates.
    """
    dataset_id: str
    date_column: str
    granularity: TimeSeriesGranularity
    metrics: List[str]
    points: List[TimeSeriesPoint]
    growth_summary: Dict[str, PeriodOverPeriodGrowth] = Field(default_factory=dict)
    execution_time_ms: float

    model_config = ConfigDict(from_attributes=True)
