from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class NegativeMeasureHandling(str, Enum):
    FLAG = "flag"
    NULLIFY = "nullify"
    ABS = "abs"
    DROP_ROW = "drop_row"


class MissingValueHandling(str, Enum):
    KEEP = "keep"
    DROP_ROW = "drop_row"
    FILL_MEAN = "fill_mean"
    FILL_MEDIAN = "fill_median"
    FILL_MODE = "fill_mode"


class InvalidDateHandling(str, Enum):
    COERCE_NULL = "coerce_null"
    DROP_ROW = "drop_row"


class CleaningPolicy(BaseModel):
    trim_whitespace: bool = Field(True, description="Trim leading and trailing whitespace in string columns")
    standardize_column_names: bool = Field(True, description="Convert column names to clean snake_case")
    drop_duplicates: bool = Field(False, description="Remove exact duplicate rows")
    handle_negative_measures: NegativeMeasureHandling = Field(
        NegativeMeasureHandling.FLAG,
        description="Policy for negative values in non-negative measure columns",
    )
    handle_missing_values: MissingValueHandling = Field(
        MissingValueHandling.KEEP,
        description="Strategy for handling null / missing values",
    )
    handle_invalid_dates: InvalidDateHandling = Field(
        InvalidDateHandling.COERCE_NULL,
        description="Strategy for unparseable date values",
    )
    coerce_currency_strings: bool = Field(
        True,
        description="Extract and parse numeric values from currency/percentage strings (e.g. '$1,200.00')",
    )


class OutlierDetectionResult(BaseModel):
    column_name: str = Field(..., description="Column evaluated for outliers")
    method: str = Field("IQR", description="Detection method used (e.g. IQR, Z-Score)")
    lower_bound: float = Field(..., description="Calculated lower outlier threshold (Q1 - 1.5*IQR)")
    upper_bound: float = Field(..., description="Calculated upper outlier threshold (Q3 + 1.5*IQR)")
    outlier_count: int = Field(..., description="Number of rows outside the threshold")
    outlier_percentage: float = Field(..., description="Percentage of outlier values")
    sample_outliers: List[float] = Field(default_factory=list, description="Sample outlier values detected")


class ColumnQualityIssue(BaseModel):
    column_name: str = Field(..., description="Column with quality issue")
    issue_type: str = Field(..., description="Category: invalid_date, negative_measure, malformed_numeric, high_nulls, whitespace")
    affected_rows: int = Field(..., description="Number of affected rows")
    affected_percentage: float = Field(..., description="Percentage of affected rows")
    description: str = Field(..., description="Explanation of issue")
    sample_problematic_values: List[Any] = Field(default_factory=list, description="Samples of problematic entries")


class DataQualityReport(BaseModel):
    dataset_id: str = Field(..., description="Associated dataset identifier")
    quality_score: float = Field(..., description="Overall health score (0-100)")
    total_rows: int = Field(..., description="Total rows in raw dataset")
    clean_rows: int = Field(..., description="Total rows in clean dataset")
    dropped_rows: int = Field(0, description="Rows dropped during normalization")
    issues_summary: Dict[str, int] = Field(default_factory=dict, description="Summary counts by issue category")
    column_issues: List[ColumnQualityIssue] = Field(default_factory=list, description="Detailed per-column issues")
    outliers: List[OutlierDetectionResult] = Field(default_factory=list, description="Detected statistical outliers")
    cleaning_actions_taken: List[str] = Field(default_factory=list, description="Log of cleaning actions performed")
    clean_file_path: Optional[str] = Field(None, description="Path to the clean parquet representation")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Report timestamp")

    model_config = ConfigDict(from_attributes=True)
