import re
from typing import Tuple
import polars as pl
from app.schemas.profile import ColumnRole, ColumnType

# Common date patterns in string formats
DATE_PATTERNS = [
    r"^\d{4}-\d{2}-\d{2}$",  # YYYY-MM-DD
    r"^\d{4}/\d{2}/\d{2}$",  # YYYY/MM/DD
    r"^\d{2}/\d{2}/\d{4}$",  # MM/DD/YYYY or DD/MM/YYYY
    r"^\d{2}-\d{2}-\d{4}$",  # MM-DD-YYYY or DD-MM-YYYY
    r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}",  # ISO datetime
]

ID_NAME_PATTERNS = re.compile(
    r"(^id$|_id$|^id_|_uuid$|_code$|_key$|^sku$|^order_id$|^customer_id$|^product_id$|^transaction_id$)",
    re.IGNORECASE,
)

DATE_NAME_PATTERNS = re.compile(
    r"(date|time|timestamp|created_at|updated_at|order_date|ship_date|purchase_date|dob|year|month|quarter)",
    re.IGNORECASE,
)

MEASURE_NAME_PATTERNS = re.compile(
    r"(price|cost|sales|revenue|profit|margin|amount|qty|quantity|units|total|discount|rate|fee|tax|salary|balance|count)",
    re.IGNORECASE,
)


class TypeDetector:
    """
    Infers physical/logical data types and analytical business roles for Polars series.
    """

    @classmethod
    def detect_column_type(cls, series: pl.Series) -> ColumnType:
        """
        Determines the physical or logical type of a Polars series.
        """
        dtype = series.dtype

        # Native numeric types
        if dtype.is_numeric() or dtype.is_decimal():
            return ColumnType.NUMERIC

        # Native date / datetime
        if dtype == pl.Date:
            return ColumnType.DATE
        if dtype == pl.Datetime or dtype == pl.Time or dtype == pl.Duration:
            return ColumnType.DATETIME

        # Native boolean
        if dtype == pl.Boolean:
            return ColumnType.BOOLEAN

        # String / Categorical analysis
        if dtype == pl.String or dtype == pl.Categorical:
            # Sample non-null values to test for date strings
            non_null_samples = series.drop_nulls().head(100).to_list()
            if non_null_samples:
                str_samples = [str(x).strip() for x in non_null_samples if str(x).strip()]
                if str_samples:
                    date_matches = 0
                    for val in str_samples:
                        if any(re.match(pattern, val) for pattern in DATE_PATTERNS):
                            date_matches += 1
                    if date_matches / len(str_samples) >= 0.8:
                        return ColumnType.DATE

            return ColumnType.CATEGORICAL

        return ColumnType.UNKNOWN

    @classmethod
    def infer_column_role(
        cls,
        name: str,
        detected_type: ColumnType,
        total_rows: int,
        unique_count: int,
    ) -> ColumnRole:
        """
        Infers the analytical role (measure, dimension, time_dimension, id).
        """
        uniqueness_ratio = unique_count / total_rows if total_rows > 0 else 0.0
        clean_name = name.strip()

        # Date types are always time dimensions
        if detected_type in (ColumnType.DATE, ColumnType.DATETIME):
            return ColumnRole.TIME_DIMENSION

        # Boolean types are dimensions
        if detected_type == ColumnType.BOOLEAN:
            return ColumnRole.DIMENSION

        # Numeric types
        if detected_type == ColumnType.NUMERIC:
            # Check if name strongly suggests an ID (e.g. Order_ID, Customer_ID, Zip_Code)
            if ID_NAME_PATTERNS.search(clean_name):
                return ColumnRole.ID
            # If every row is unique integer and row count > 10
            if uniqueness_ratio == 1.0 and total_rows > 10 and not MEASURE_NAME_PATTERNS.search(clean_name):
                return ColumnRole.ID
            return ColumnRole.MEASURE

        # Categorical / String types
        if detected_type == ColumnType.CATEGORICAL:
            if ID_NAME_PATTERNS.search(clean_name):
                return ColumnRole.ID
            if uniqueness_ratio >= 0.95 and total_rows > 20:
                return ColumnRole.ID
            return ColumnRole.DIMENSION

        return ColumnRole.UNKNOWN

    @classmethod
    def analyze_series(
        cls,
        series: pl.Series,
        total_rows: int,
        unique_count: int,
    ) -> Tuple[ColumnType, ColumnRole]:
        """
        Returns both detected type and inferred role.
        """
        col_type = cls.detect_column_type(series)
        col_role = cls.infer_column_role(series.name, col_type, total_rows, unique_count)
        return col_type, col_role
