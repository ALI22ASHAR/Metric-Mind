from pathlib import Path
from typing import Union
import polars as pl

NULL_VALUES = ["", "NA", "N/A", "null", "NULL", "none", "NONE", "NaN", "nan", "-"]


class DatasetLoader:
    """
    Utility to load CSV and Excel datasets into Polars DataFrames.
    """

    @staticmethod
    def load_polars_dataframe(file_path: Union[str, Path]) -> pl.DataFrame:
        """
        Reads a CSV or Excel file from disk into a Polars DataFrame.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Dataset file does not exist at '{file_path}'.")

        ext = path.suffix.lower()
        if ext == ".csv":
            return pl.read_csv(
                str(path),
                infer_schema_length=10000,
                ignore_errors=True,
                null_values=NULL_VALUES,
                truncate_ragged_lines=True,
            )
        elif ext in [".xlsx", ".xls"]:
            return pl.read_excel(str(path))
        else:
            raise ValueError(f"Unsupported file format '{ext}'.")


dataset_loader = DatasetLoader()
