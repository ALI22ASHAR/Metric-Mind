from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class WidgetType(str, Enum):
    KPI_CARD = "kpi_card"
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    AREA_CHART = "area_chart"
    TABLE = "table"


class GridPosition(BaseModel):
    """
    12-column responsive grid coordinates.
    """
    x: int = Field(0, ge=0, le=11, description="Horizontal grid column index (0-11)")
    y: int = Field(0, ge=0, description="Vertical grid row index")
    w: int = Field(6, ge=1, le=12, description="Grid column span width (1-12)")
    h: int = Field(4, ge=1, le=20, description="Grid row span height")


class WidgetConfig(BaseModel):
    """
    Declarative specification for a single dashboard visual widget.
    """
    id: str = Field(..., description="Unique widget identifier, e.g., 'w_rev_trend'")
    type: WidgetType = Field(WidgetType.LINE_CHART, description="Visual widget type")
    title: str = Field(..., description="Display title of the widget")
    description: Optional[str] = Field(None, description="Subtitle or explanatory text")
    metric_id: Optional[str] = Field(None, description="Primary KPI metric ID (for KPI cards)")
    dimension: Optional[str] = Field(None, description="Dimension column name to group by")
    metrics: List[str] = Field(default_factory=list, description="List of metric IDs to render")
    granularity: Optional[str] = Field(None, description="Time interval for temporal charts (day, week, month, quarter, year)")
    position: GridPosition = Field(default_factory=GridPosition, description="Grid layout position")
    options: Dict[str, Any] = Field(default_factory=dict, description="Custom visual options (colors, legend, formatting)")

    model_config = ConfigDict(from_attributes=True)


class DashboardFilterConfig(BaseModel):
    """
    Declarative interactive filter widget specification.
    """
    id: str = Field(..., description="Unique filter ID")
    column: str = Field(..., description="Target dataset column to filter on")
    label: str = Field(..., description="User-facing filter label")
    filter_type: str = Field("select", description="UI control type: 'select', 'date_range', 'multi_select'")
    options: Optional[List[str]] = Field(None, description="Available categorical options")

    model_config = ConfigDict(from_attributes=True)


class DashboardSpec(BaseModel):
    """
    Complete declarative specification for an interactive business intelligence dashboard.
    """
    id: str = Field(..., description="Unique dashboard ID, e.g., 'dsh_... '")
    dataset_id: str = Field(..., description="Target dataset ID")
    title: str = Field("Executive Business Intelligence Dashboard", description="Dashboard title")
    subtitle: Optional[str] = Field(None, description="Dashboard subtitle")
    theme: str = Field("dark", description="Visual theme ('dark', 'light')")
    widgets: List[WidgetConfig] = Field(default_factory=list, description="Collection of visual widgets")
    filters: List[DashboardFilterConfig] = Field(default_factory=list, description="Global interactive filters")
    version: int = Field(1, description="Schema specification version")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class DashboardCreate(BaseModel):
    title: Optional[str] = Field(None, description="Custom dashboard title")
    subtitle: Optional[str] = Field(None, description="Custom subtitle")
    theme: str = Field("dark", description="Visual theme")


class DashboardUpdate(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    theme: Optional[str] = None
    widgets: Optional[List[WidgetConfig]] = None
    filters: Optional[List[DashboardFilterConfig]] = None


class DashboardDataResponse(BaseModel):
    """
    Full payload containing the declarative dashboard spec and live evaluated data for every widget.
    """
    spec: DashboardSpec
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Hydrated live analytical data keyed by widget ID",
    )
    execution_time_ms: float = Field(0.0, description="Total backend hydration latency in milliseconds")

    model_config = ConfigDict(from_attributes=True)
