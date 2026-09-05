from datetime import datetime, timezone
from typing import Any, List
import polars as pl

from app.ingestion.quality import DataQualityAnalyzer
from app.ingestion.type_detector import TypeDetector
from app.schemas.profile import (
    ColumnProfile,
    ColumnType,
    DatasetProfileResponse,
    DatasetSummaryStats,
    DateStats,
    NumericStats,
)


class DatasetProfiler:
    """
    High-performance dataset profiling engine using Polars.
    """

    @classmethod
    def profile_dataframe(cls, df: pl.DataFrame, dataset_id: str) -> DatasetProfileResponse:
        """
        Profiles a Polars DataFrame and returns a comprehensive DatasetProfileResponse.
        """
        total_rows = df.height
        total_cols = df.width

        # 1. Structural summary & duplicates
        if total_rows > 0:
            unique_rows = df.unique().height
            duplicate_rows = total_rows - unique_rows
            duplicate_pct = round((duplicate_rows / total_rows) * 100, 2)
        else:
            duplicate_rows = 0
            duplicate_pct = 0.0

        memory_kb = round(df.estimated_size() / 1024.0, 2)

        summary = DatasetSummaryStats(
            row_count=total_rows,
            column_count=total_cols,
            duplicate_rows=duplicate_rows,
            duplicate_rows_percentage=duplicate_pct,
            estimated_memory_kb=memory_kb,
        )

        column_profiles: List[ColumnProfile] = []

        # 2. Analyze each column
        for col_name in df.columns:
            series = df[col_name]
            null_count = series.null_count()
            null_pct = round((null_count / total_rows) * 100, 2) if total_rows > 0 else 0.0
            unique_count = series.n_unique()
            uniqueness_pct = round((unique_count / total_rows) * 100, 2) if total_rows > 0 else 0.0

            # Detect type and infer analytical role
            col_type, col_role = TypeDetector.analyze_series(series, total_rows, unique_count)

            # Sample non-null values
            non_nulls = series.drop_nulls().head(5).to_list()
            sample_values: List[Any] = []
            for item in non_nulls:
                if isinstance(item, (datetime, pl.Date, pl.Datetime)):
                    sample_values.append(str(item))
                elif isinstance(item, float):
                    sample_values.append(round(item, 4))
                else:
                    sample_values.append(item)

            numeric_stats = None
            date_stats = None

            # Numeric statistics calculation
            if col_type == ColumnType.NUMERIC and total_rows > null_count:
                try:
                    s_valid = series.drop_nulls()
                    if s_valid.len() > 0:
                        min_v = float(s_valid.min()) if s_valid.min() is not None else None
                        max_v = float(s_valid.max()) if s_valid.max() is not None else None
                        mean_v = float(s_valid.mean()) if s_valid.mean() is not None else None
                        median_v = float(s_valid.median()) if s_valid.median() is not None else None
                        std_v = float(s_valid.std()) if s_valid.len() > 1 and s_valid.std() is not None else None
                        q25_v = float(s_valid.quantile(0.25)) if s_valid.len() > 0 else None
                        q75_v = float(s_valid.quantile(0.75)) if s_valid.len() > 0 else None

                        numeric_stats = NumericStats(
                            min=round(min_v, 4) if min_v is not None else None,
                            max=round(max_v, 4) if max_v is not None else None,
                            mean=round(mean_v, 4) if mean_v is not None else None,
                            median=round(median_v, 4) if median_v is not None else None,
                            std_dev=round(std_v, 4) if std_v is not None else None,
                            q25=round(q25_v, 4) if q25_v is not None else None,
                            q75=round(q75_v, 4) if q75_v is not None else None,
                        )
                except Exception:
                    pass

            # Date statistics calculation
            elif col_type in (ColumnType.DATE, ColumnType.DATETIME) and total_rows > null_count:
                try:
                    s_valid = series.drop_nulls()
                    min_d = str(s_valid.min()) if s_valid.min() is not None else None
                    max_d = str(s_valid.max()) if s_valid.max() is not None else None
                    duration_days = None

                    # If datetime / date series can compute duration
                    if min_d and max_d:
                        try:
                            # Attempt date parse if string
                            d1 = datetime.fromisoformat(min_d[:10])
                            d2 = datetime.fromisoformat(max_d[:10])
                            duration_days = (d2 - d1).days
                        except Exception:
                            pass

                    date_stats = DateStats(
                        min_date=min_d,
                        max_date=max_d,
                        duration_days=duration_days,
                    )
                except Exception:
                    pass

            column_profiles.append(
                ColumnProfile(
                    name=col_name,
                    detected_type=col_type,
                    role=col_role,
                    null_count=null_count,
                    null_percentage=null_pct,
                    unique_count=unique_count,
                    uniqueness_percentage=uniqueness_pct,
                    sample_values=sample_values,
                    numeric_stats=numeric_stats,
                    date_stats=date_stats,
                )
            )

        # 3. Data quality warnings
        quality_warnings = DataQualityAnalyzer.evaluate_quality(
            total_rows=total_rows,
            duplicate_rows=duplicate_rows,
            column_profiles=column_profiles,
        )

        return DatasetProfileResponse(
            dataset_id=dataset_id,
            summary=summary,
            columns_info=column_profiles,
            quality_warnings=quality_warnings,
            created_at=datetime.now(timezone.utc),
        )


dataset_profiler = DatasetProfiler()
