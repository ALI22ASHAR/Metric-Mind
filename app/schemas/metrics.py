from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MetricType(str, Enum):
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    COUNT = "count"
    QUANTITY = "quantity"
    RATIO = "ratio"


class MetricDefinition(BaseModel):
    """
    Metadata specification for a computable business metric.
    """
    id: str = Field(..., description="Unique metric identifier, e.g., 'total_revenue'")
    name: str = Field(..., description="Machine-friendly metric name")
    label: str = Field(..., description="User-facing title, e.g., 'Total Revenue'")
    description: str = Field(..., description="Explanation of what this metric calculates")
    metric_type: MetricType = Field(MetricType.CURRENCY, description="Data type of the metric")
    unit: str = Field("$", description="Display unit prefix or suffix, e.g. '$', '%', 'units'")
    is_computable: bool = Field(True, description="Whether this metric can be calculated with current semantic mappings")
    required_concepts: List[str] = Field(default_factory=list, description="Semantic concepts required to calculate this KPI")
    sql_template: str = Field(..., description="Parameterized SQL expression template")
    format_spec: str = Field("${:,.2f}", description="String formatting template")

    model_config = ConfigDict(from_attributes=True)


class MetricResult(BaseModel):
    """
    Evaluated value and formatted representation of a metric.
    """
    metric_id: str
    name: str
    label: str
    value: Optional[float] = None
    formatted_value: str = "N/A"
    metric_type: MetricType = MetricType.CURRENCY
    unit: str = "$"

    model_config = ConfigDict(from_attributes=True)


class DatasetMetricsSummary(BaseModel):
    """
    Collection of computable KPIs and calculated summary values for a dataset.
    """
    dataset_id: str
    total_computable_metrics: int
    computable_metrics: List[MetricDefinition]
    metrics: Dict[str, MetricResult]

    model_config = ConfigDict(from_attributes=True)
