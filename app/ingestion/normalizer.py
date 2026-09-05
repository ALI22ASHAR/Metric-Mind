from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import polars as pl

from app.ingestion.outliers import outlier_detector
from app.ingestion.profiler import dataset_profiler
from app.schemas.profile import ColumnRole, ColumnType
from app.schemas.quality import (
    CleaningPolicy,
    ColumnQualityIssue,
    DataQualityReport,
    InvalidDateHandling,
    MissingValueHandling,
    NegativeMeasureHandling,
)

NON_NEGATIVE_MEASURES = re.compile(r"(price|cost|sales|revenue|qty|quantity|units|count|fee|tax|salary)", re.IGNORECASE)


class DatasetNormalizer:
    """
    Cleans, normalizes, and generates a validated analytical representation (Parquet)
    while recording data quality scores and audit trails.
    """

    @classmethod
    def clean_column_name(cls, col_name: str) -> str:
        """
        Converts column names to clean, standardized snake_case.
        Example: 'Order ID #' -> 'order_id', 'Sale Price ($)' -> 'sale_price'
        """
        s = re.sub(r"\([^)]*\)", "", col_name)
        s = re.sub(r"[^a-zA-Z0-9]+", "_", s)
        s = s.strip("_").lower()
        return s if s else "col"

    @classmethod
    def calculate_quality_score(
        cls,
        total_rows: int,
        duplicate_rows: int,
        issues: List[ColumnQualityIssue],
        total_cols: int,
    ) -> float:
        """
        Computes a comprehensive data quality health score from 0 to 100.
        """
        if total_rows == 0:
            return 0.0

        score = 100.0

        # Duplicate records penalty (up to -20 points)
        dup_pct = (duplicate_rows / total_rows) * 100.0
        score -= min(dup_pct * 0.5, 20.0)

        # Issues penalties
        for issue in issues:
            impact_pct = issue.affected_percentage
            if issue.issue_type == "high_nulls":
                score -= min(impact_pct * 0.3, 15.0)
            elif issue.issue_type == "missing_values":
                score -= min(impact_pct * 0.15, 8.0)
            elif issue.issue_type == "negative_measure":
                score -= min(impact_pct * 0.25, 10.0)
            elif issue.issue_type == "invalid_date":
                score -= min(impact_pct * 0.25, 10.0)
            elif issue.issue_type == "malformed_numeric":
                score -= min(impact_pct * 0.2, 8.0)

        return max(round(score, 1), 0.0)

    @classmethod
    def normalize_dataset(
        cls,
        raw_df: pl.DataFrame,
        dataset_id: str,
        output_dir: Path,
        policy: Optional[CleaningPolicy] = None,
    ) -> Tuple[pl.DataFrame, DataQualityReport, str]:
        """
        Applies cleaning policy, detects quality defects, exports clean Parquet,
        and produces the DataQualityReport.
        """
        policy = policy or CleaningPolicy()
        actions_taken: List[str] = []
        column_issues: List[ColumnQualityIssue] = []
        issues_summary: Dict[str, int] = {}

        df = raw_df.clone()
        raw_row_count = df.height
        raw_col_count = df.width

        # 1. Profile initial dataset
        profile_res = dataset_profiler.profile_dataframe(df, dataset_id)
        cols_map = {col.name: col for col in profile_res.columns_info}

        # 2. Standardize column names
        name_mapping: Dict[str, str] = {}
        if policy.standardize_column_names:
            renamed_cols = {}
            for col in df.columns:
                cleaned = cls.clean_column_name(col)
                final_name = cleaned
                idx = 1
                while final_name in renamed_cols.values():
                    final_name = f"{cleaned}_{idx}"
                    idx += 1
                renamed_cols[col] = final_name
                name_mapping[col] = final_name

            df = df.rename(renamed_cols)
            actions_taken.append(f"Standardized {len(renamed_cols)} column names to snake_case.")
        else:
            name_mapping = {col: col for col in df.columns}

        # 3. String trimming & currency / numeric coercion
        for orig_name, clean_name in name_mapping.items():
            col_prof = cols_map.get(orig_name)
            series = df[clean_name]

            # Whitespace trimming
            if policy.trim_whitespace and (series.dtype == pl.String or series.dtype == pl.Categorical):
                df = df.with_columns(pl.col(clean_name).cast(pl.String).str.strip_chars())

            # Currency / numeric string coercion
            if policy.coerce_currency_strings and series.dtype == pl.String:
                if (col_prof and col_prof.role == ColumnRole.MEASURE) or NON_NEGATIVE_MEASURES.search(clean_name):
                    try:
                        cleaned_s = (
                            pl.col(clean_name)
                            .str.replace_all(r"[\$,€,£,¥,\%]", "")
                            .str.replace_all(r"\((.*?)\)", "-$1")
                            .str.strip_chars()
                            .cast(pl.Float64, strict=False)
                        )
                        df = df.with_columns(cleaned_s)
                        actions_taken.append(f"Coerced formatted strings in measure column '{clean_name}' to numeric Float64.")
                    except Exception:
                        pass

        # 4. Check negative values in measure columns & apply policy
        for orig_name, clean_name in name_mapping.items():
            if clean_name in df.columns and df[clean_name].dtype.is_numeric():
                if NON_NEGATIVE_MEASURES.search(clean_name):
                    neg_count = df.filter(pl.col(clean_name) < 0).height
                    if neg_count > 0:
                        neg_pct = round((neg_count / raw_row_count) * 100, 2)
                        column_issues.append(
                            ColumnQualityIssue(
                                column_name=clean_name,
                                issue_type="negative_measure",
                                affected_rows=neg_count,
                                affected_percentage=neg_pct,
                                description=f"Measure '{clean_name}' contains {neg_count} negative values ({neg_pct}%).",
                            )
                        )
                        issues_summary["negative_measures"] = issues_summary.get("negative_measures", 0) + neg_count

                        if policy.handle_negative_measures == NegativeMeasureHandling.ABS:
                            df = df.with_columns(pl.col(clean_name).abs())
                            actions_taken.append(f"Converted {neg_count} negative values in '{clean_name}' to absolute values.")
                        elif policy.handle_negative_measures == NegativeMeasureHandling.NULLIFY:
                            df = df.with_columns(
                                pl.when(pl.col(clean_name) < 0).then(None).otherwise(pl.col(clean_name)).alias(clean_name)
                            )
                            actions_taken.append(f"Nullified {neg_count} negative values in '{clean_name}'.")
                        elif policy.handle_negative_measures == NegativeMeasureHandling.DROP_ROW:
                            df = df.filter(pl.col(clean_name) >= 0)
                            actions_taken.append(f"Dropped {neg_count} rows with negative values in '{clean_name}'.")

        # 5. Missing values recording
        for col_name in df.columns:
            null_count = df[col_name].null_count()
            if null_count > 0:
                null_pct = round((null_count / raw_row_count) * 100, 2)
                issue_type = "high_nulls" if null_pct > 50 else "missing_values"
                column_issues.append(
                    ColumnQualityIssue(
                        column_name=col_name,
                        issue_type=issue_type,
                        affected_rows=null_count,
                        affected_percentage=null_pct,
                        description=f"Column '{col_name}' has {null_count} missing values ({null_pct}%).",
                    )
                )
                issues_summary["missing_values"] = issues_summary.get("missing_values", 0) + null_count

        # 6. Duplicate handling policy
        duplicate_rows = profile_res.summary.duplicate_rows
        if duplicate_rows > 0:
            issues_summary["duplicate_rows"] = duplicate_rows
            if policy.drop_duplicates:
                before_count = df.height
                df = df.unique()
                dropped = before_count - df.height
                actions_taken.append(f"Removed {dropped} exact duplicate records.")

        # 7. Outliers detection using clean column names
        clean_col_profiles = []
        for col_p in profile_res.columns_info:
            clean_name = name_mapping.get(col_p.name, col_p.name)
            clean_col_profiles.append(
                col_p.model_copy(update={"name": clean_name})
            )
        outliers = outlier_detector.detect_dataset_outliers(df, clean_col_profiles)

        # 8. Calculate quality score
        quality_score = cls.calculate_quality_score(
            total_rows=raw_row_count,
            duplicate_rows=duplicate_rows,
            issues=column_issues,
            total_cols=raw_col_count,
        )

        # 9. Export Clean Analytical Parquet representation
        clean_file_path = output_dir / "clean_data.parquet"
        output_dir.mkdir(parents=True, exist_ok=True)
        df.write_parquet(str(clean_file_path))
        actions_taken.append(f"Persisted clean analytical representation as Parquet ({df.height} rows, {df.width} cols).")

        clean_row_count = df.height
        dropped_rows = raw_row_count - clean_row_count

        report = DataQualityReport(
            dataset_id=dataset_id,
            quality_score=quality_score,
            total_rows=raw_row_count,
            clean_rows=clean_row_count,
            dropped_rows=dropped_rows,
            issues_summary=issues_summary,
            column_issues=column_issues,
            outliers=outliers,
            cleaning_actions_taken=actions_taken,
            clean_file_path=str(clean_file_path),
            created_at=datetime.now(timezone.utc),
        )

        return df, report, str(clean_file_path)


dataset_normalizer = DatasetNormalizer()
