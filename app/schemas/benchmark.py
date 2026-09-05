from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MetricBenchmarkDiff(BaseModel):
    metric_id: str
    label: str
    base_dataset_value: float
    target_dataset_value: float
    delta_value: float
    delta_percentage: float
    is_positive_growth: bool

    model_config = ConfigDict(from_attributes=True)


class DatasetBenchmarkResponse(BaseModel):
    base_dataset_id: str
    target_dataset_id: str
    metric_comparisons: List[MetricBenchmarkDiff]
    overall_summary: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
