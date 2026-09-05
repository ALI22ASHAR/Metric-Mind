from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AnomalySeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AnomalyType(str, Enum):
    SPIKE = "spike"
    DROP = "drop"
    OUTLIER = "outlier"


class DimensionContribution(BaseModel):
    dimension: str = Field(..., description="Categorical dimension name (e.g. 'Category')")
    value: str = Field(..., description="Dimension value (e.g. 'Electronics')")
    prior_value: float = Field(..., description="Prior period value")
    current_value: float = Field(..., description="Current period value")
    delta: float = Field(..., description="Absolute change")
    contribution_percentage: float = Field(..., description="Share of total shift (0-100%)")

    model_config = ConfigDict(from_attributes=True)


class DetectedAnomaly(BaseModel):
    id: str = Field(..., description="Unique anomaly ID")
    metric: str = Field(..., description="Target metric name")
    period: str = Field(..., description="Temporal period when anomaly occurred (e.g. '2024-02')")
    actual_value: float = Field(..., description="Observed metric value")
    expected_value: float = Field(..., description="Expected baseline mean")
    deviation_percentage: float = Field(..., description="Percentage deviation from expected")
    z_score: float = Field(..., description="Statistical Z-score")
    severity: AnomalySeverity = Field(..., description="Severity level: critical, warning, info")
    anomaly_type: AnomalyType = Field(..., description="Anomaly category: spike, drop, outlier")
    root_causes: List[DimensionContribution] = Field(default_factory=list, description="Top dimensional drivers")
    explanation: str = Field(..., description="Human-readable root cause explanation")

    model_config = ConfigDict(from_attributes=True)


class AnomalyReportResponse(BaseModel):
    dataset_id: str
    total_anomalies: int
    anomalies: List[DetectedAnomaly]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
