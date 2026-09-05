from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ForecastModelType(str, Enum):
    LINEAR_TREND = "linear_trend"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    AUTO = "auto"


class ForecastPoint(BaseModel):
    period: str = Field(..., description="Projected period (e.g. '2024-03')")
    predicted_value: float = Field(..., description="Projected central forecast value")
    lower_bound_80: float = Field(..., description="80% confidence interval lower bound")
    upper_bound_80: float = Field(..., description="80% confidence interval upper bound")
    lower_bound_95: float = Field(..., description="95% confidence interval lower bound")
    upper_bound_95: float = Field(..., description="95% confidence interval upper bound")

    model_config = ConfigDict(from_attributes=True)


class ForecastRequest(BaseModel):
    metric: str = Field("total_revenue", description="Target metric to project")
    periods_ahead: int = Field(3, ge=1, le=24, description="Number of future periods to project")
    model_type: ForecastModelType = Field(ForecastModelType.AUTO, description="Forecasting algorithm")

    model_config = ConfigDict(from_attributes=True)


class ForecastResponse(BaseModel):
    dataset_id: str
    metric: str
    model_used: ForecastModelType
    historical_periods_count: int
    forecast: List[ForecastPoint]
    growth_rate_projected_pct: float
    summary: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
