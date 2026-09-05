import re
from typing import List, Optional
import polars as pl

from app.schemas.profile import (
    ColumnProfile,
    ColumnRole,
    ColumnType,
    DataQualityWarning,
    WarningSeverity,
)

NON_NEGATIVE_MEASURES = re.compile(
    r"(price|cost|sales|revenue|qty|quantity|units|count|fee|tax|salary)",
    re.IGNORECASE,
)


class DataQualityAnalyzer:
    """
    Evaluates dataset and column profiles to identify data quality anomalies and hygiene issues.
    """

    @classmethod
    def evaluate_quality(
        cls,
        total_rows: int,
        duplicate_rows: int,
        column_profiles: List[ColumnProfile],
    ) -> List[DataQualityWarning]:
        """
        Generates a comprehensive list of data quality warnings.
        """
        warnings: List[DataQualityWarning] = []

        # 1. Dataset-level duplicate check
        if duplicate_rows > 0 and total_rows > 0:
            dup_pct = round((duplicate_rows / total_rows) * 100, 2)
            severity = WarningSeverity.CRITICAL if dup_pct > 20 else WarningSeverity.WARNING
            warnings.append(
                DataQualityWarning(
                    column_name=None,
                    warning_type="duplicate_rows",
                    severity=severity,
                    message=f"Dataset contains {duplicate_rows} duplicate rows ({dup_pct}% of total records).",
                    metric_value=float(duplicate_rows),
                )
            )

        # 2. Column-level checks
        for col in column_profiles:
            # Check missing values
            if col.null_percentage > 50.0:
                warnings.append(
                    DataQualityWarning(
                        column_name=col.name,
                        warning_type="high_missing_values",
                        severity=WarningSeverity.CRITICAL,
                        message=f"Column '{col.name}' has {col.null_percentage}% missing values ({col.null_count} nulls).",
                        metric_value=col.null_percentage,
                    )
                )
            elif col.null_percentage >= 5.0:
                warnings.append(
                    DataQualityWarning(
                        column_name=col.name,
                        warning_type="missing_values",
                        severity=WarningSeverity.WARNING,
                        message=f"Column '{col.name}' has {col.null_percentage}% missing values ({col.null_count} nulls).",
                        metric_value=col.null_percentage,
                    )
                )

            # Check negative values in measure columns
            if col.detected_type == ColumnType.NUMERIC and col.numeric_stats:
                min_val = col.numeric_stats.min
                if min_val is not None and min_val < 0:
                    if NON_NEGATIVE_MEASURES.search(col.name):
                        warnings.append(
                            DataQualityWarning(
                                column_name=col.name,
                                warning_type="negative_values",
                                severity=WarningSeverity.WARNING,
                                message=f"Measure column '{col.name}' contains negative values (minimum: {min_val}).",
                                metric_value=min_val,
                            )
                        )

            # Check single-value / zero variance columns
            if col.unique_count == 1 and total_rows > 1:
                warnings.append(
                    DataQualityWarning(
                        column_name=col.name,
                        warning_type="constant_column",
                        severity=WarningSeverity.INFO,
                        message=f"Column '{col.name}' contains only 1 unique value across all rows.",
                        metric_value=1.0,
                    )
                )

            # Check high cardinality dimensions
            if col.role == ColumnRole.DIMENSION and col.unique_count > 500 and col.uniqueness_percentage > 70.0:
                warnings.append(
                    DataQualityWarning(
                        column_name=col.name,
                        warning_type="high_cardinality",
                        severity=WarningSeverity.INFO,
                        message=f"Dimension '{col.name}' has high cardinality with {col.unique_count} distinct values.",
                        metric_value=float(col.unique_count),
                    )
                )

        return warnings
