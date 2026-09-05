from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.dashboard import WidgetType


class KpiAggregationType(str, Enum):
    SUM = "sum"
    AVG = "avg"
    COUNT = "count"
    MIN = "min"
    MAX = "max"
    RATE = "rate"
    PERCENT_OF_TOTAL = "percent_of_total"


class KpiFormatType(str, Enum):
    NUMBER = "number"
    PERCENTAGE = "percentage"
    CURRENCY = "currency"
    DURATION = "duration"


class KpiCondition(BaseModel):
    """Numerator condition for Rate calculations (e.g. IsDelayed == True)."""
    column: Optional[str] = None
    operator: str = Field("==", description="Comparison operator: '==', '!=', '>', '>=', '<', '<='")
    value: Any = Field(True, description="Comparison target value")

    model_config = ConfigDict(extra="ignore")


class CustomKpiSpec(BaseModel):
    """
    Declarative specification for a user-constructed KPI.
    """
    label: str = Field(..., description="Display title for the custom KPI")
    column: str = Field(..., description="Target dataset column for calculation")
    aggregation: KpiAggregationType = Field(KpiAggregationType.AVG, description="Aggregation operation")
    condition: Optional[KpiCondition] = Field(None, description="Numerator condition for rate calculation")
    dimension: Optional[str] = Field(None, description="Optional categorical/temporal grouping dimension")
    output_type: Optional[str] = Field("auto", description="Visual display type: 'auto', 'kpi_card', 'bar_chart', 'line_chart', 'pie_chart', 'table'")
    format_type: Optional[KpiFormatType] = Field(KpiFormatType.NUMBER, description="Display number formatting")
    unit: Optional[str] = Field(None, description="Optional suffix unit, e.g., 'min', 'flights', '%'")
    limit: Optional[int] = Field(15, description="Max breakdown items for charts/tables")

    model_config = ConfigDict(extra="ignore")


class KpiPreviewResponse(BaseModel):
    """
    Payload returned when generating a live preview of a custom KPI.
    """
    spec: CustomKpiSpec
    resolved_widget_type: WidgetType
    suggested_visual_reason: str
    scalar_value: Optional[float] = None
    formatted_value: Optional[str] = None
    sparkline: Optional[List[Optional[float]]] = None
    rows: Optional[List[Dict[str, Any]]] = None
    dimension: Optional[str] = None
    execution_time_ms: float = 0.0

    model_config = ConfigDict(from_attributes=True)
