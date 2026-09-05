from typing import List, Optional
import polars as pl
from app.schemas.profile import ColumnProfile, ColumnRole, ColumnType
from app.schemas.quality import OutlierDetectionResult


class OutlierDetector:
    """
    Identifies statistical outliers in numeric measure columns using Interquartile Range (IQR).
    """

    @classmethod
    def detect_iqr_outliers(cls, series: pl.Series) -> Optional[OutlierDetectionResult]:
        """
        Calculates IQR boundaries for a numeric series and flags values falling outside.
        """
        valid_series = series.drop_nulls()
        n = valid_series.len()
        if n < 10:  # Insufficient data points for meaningful IQR
            return None

        try:
            q1 = float(valid_series.quantile(0.25))
            q3 = float(valid_series.quantile(0.75))
            iqr = q3 - q1

            if iqr <= 0:
                return None

            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr

            # Find outliers
            outliers = valid_series.filter(
                (valid_series < lower_bound) | (valid_series > upper_bound)
            )
            outlier_count = outliers.len()

            if outlier_count == 0:
                return None

            outlier_pct = round((outlier_count / n) * 100, 2)
            samples = [round(float(x), 4) for x in outliers.head(5).to_list()]

            return OutlierDetectionResult(
                column_name=series.name,
                method="IQR",
                lower_bound=round(lower_bound, 4),
                upper_bound=round(upper_bound, 4),
                outlier_count=outlier_count,
                outlier_percentage=outlier_pct,
                sample_outliers=samples,
            )
        except Exception:
            return None

    @classmethod
    def detect_dataset_outliers(
        cls,
        df: pl.DataFrame,
        column_profiles: List[ColumnProfile],
    ) -> List[OutlierDetectionResult]:
        """
        Runs outlier detection across all eligible numeric measure columns in a DataFrame.
        """
        results: List[OutlierDetectionResult] = []
        for col in column_profiles:
            if col.detected_type == ColumnType.NUMERIC and col.role == ColumnRole.MEASURE:
                if col.name in df.columns:
                    outlier_res = cls.detect_iqr_outliers(df[col.name])
                    if outlier_res:
                        results.append(outlier_res)

        return results


outlier_detector = OutlierDetector()
