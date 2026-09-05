from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ColumnType(str, Enum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    UNKNOWN = "unknown"


class ColumnRole(str, Enum):
    MEASURE = "measure"
    DIMENSION = "dimension"
    TIME_DIMENSION = "time_dimension"
    ID = "id"
    UNKNOWN = "unknown"


class WarningSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DataQualityWarning(BaseModel):
    column_name: Optional[str] = Field(None, description="Affected column name (null for dataset-wide warnings)")
    warning_type: str = Field(..., description="Category: missing_values, duplicate_rows, negative_values, constant_column, etc.")
    severity: WarningSeverity = Field(WarningSeverity.WARNING, description="Severity of warning")
    message: str = Field(..., description="Human-readable warning description")
    metric_value: Optional[float] = Field(None, description="Numerical metric value (e.g. percentage or count)")


class NumericStats(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std_dev: Optional[float] = None
    q25: Optional[float] = None
    q75: Optional[float] = None


class DateStats(BaseModel):
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    duration_days: Optional[int] = None


class ColumnProfile(BaseModel):
    name: str = Field(..., description="Column header name")
    detected_type: ColumnType = Field(..., description="Detected logical/physical data type")
    role: ColumnRole = Field(..., description="Inferred analytical role: measure, dimension, time_dimension, id")
    null_count: int = Field(0, description="Total missing/null values")
    null_percentage: float = Field(0.0, description="Percentage of missing values (0-100)")
    unique_count: int = Field(0, description="Cardinality / unique count")
    uniqueness_percentage: float = Field(0.0, description="Percentage of unique values (0-100)")
    sample_values: List[Any] = Field(default_factory=list, description="Top representative sample values")
    numeric_stats: Optional[NumericStats] = Field(None, description="Descriptive statistics if numeric")
    date_stats: Optional[DateStats] = Field(None, description="Date boundaries if temporal")


class DatasetSummaryStats(BaseModel):
    row_count: int = Field(..., description="Total row count")
    column_count: int = Field(..., description="Total column count")
    duplicate_rows: int = Field(0, description="Number of exact duplicate rows")
    duplicate_rows_percentage: float = Field(0.0, description="Percentage of duplicate rows (0-100)")
    estimated_memory_kb: float = Field(0.0, description="Estimated in-memory footprint in KB")


class DatasetProfileResponse(BaseModel):
    dataset_id: str = Field(..., description="Associated dataset ID")
    summary: DatasetSummaryStats = Field(..., description="Dataset structural summary")
    columns_info: List[ColumnProfile] = Field(..., description="Detailed profile for each column")
    quality_warnings: List[DataQualityWarning] = Field(default_factory=list, description="List of data quality issues")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Profiling generation timestamp")

    model_config = ConfigDict(from_attributes=True)
