from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class FilterOperator(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    IN = "in"
    NOT_IN = "not_in"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    BETWEEN = "between"
    LIKE = "like"


class DimensionFilter(BaseModel):
    """
    SQL filter predicate applied to analytical queries.
    """
    column: str = Field(..., description="Target column name")
    operator: FilterOperator = Field(FilterOperator.EQ, description="Filter operator")
    value: Any = Field(..., description="Filter comparison value or list of values")


class BreakdownRequest(BaseModel):
    """
    Request payload to aggregate metrics grouped by a dimension.
    """
    dimension: str = Field(..., description="Column name to group by, e.g. 'category', 'city', 'product'")
    metrics: List[str] = Field(default_factory=lambda: ["total_revenue"], description="List of metric IDs to calculate")
    filters: Optional[List[DimensionFilter]] = Field(default=None, description="Optional filters")
    limit: int = Field(20, ge=1, le=1000, description="Max rows to return")
    sort_by: Optional[str] = Field(None, description="Metric or dimension column to sort by")
    ascending: bool = Field(False, description="Sort direction")


class BreakdownResponse(BaseModel):
    """
    Response containing multi-dimensional aggregated rows.
    """
    dimension: str
    metrics: List[str]
    rows: List[Dict[str, Any]]
    total_distinct_groups: int
    execution_time_ms: float

    model_config = ConfigDict(from_attributes=True)


class RawQueryRequest(BaseModel):
    query: str = Field(..., description="Read-only SQL query to execute against the clean Parquet file")


class RawQueryResponse(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: float

    model_config = ConfigDict(from_attributes=True)
