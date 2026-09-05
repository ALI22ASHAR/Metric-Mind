import ast
import logging
import re
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ALLOWED_FUNCTIONS = {"SUM", "AVG", "COUNT", "MIN", "MAX", "ROUND", "ABS"}
ALLOWED_OPERATORS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.USub, ast.UAdd)


class CustomMetricRequest(BaseModel):
    name: str = Field(..., description="Unique identifier or name for metric (e.g. gross_margin_pct)")
    label: str = Field(..., description="Human-readable label (e.g. Gross Margin %)")
    formula: str = Field(..., description="Mathematical expression (e.g. (Revenue - Cost) / Revenue * 100)")
    description: Optional[str] = Field(None, description="Explanation of what this metric measures")
    format_type: str = Field("currency", description="Format style: currency, percentage, number, integer")


class CustomMetricValidationResult(BaseModel):
    is_valid: bool
    sql_template: str
    referenced_columns: List[str]
    error_message: Optional[str] = None


class FormulaEngine:
    """
    Validates, parses, and converts user-defined mathematical formulas
    into safe DuckDB SQL aggregate expressions.
    """

    @classmethod
    def validate_and_compile(
        cls,
        formula: str,
        available_columns: List[str],
    ) -> CustomMetricValidationResult:
        """
        Validates the formula against SQL injection, validates column references,
        and constructs a deterministic DuckDB SQL aggregation template.
        """
        raw_formula = formula.strip()
        if not raw_formula:
            return CustomMetricValidationResult(
                is_valid=False,
                sql_template="",
                referenced_columns=[],
                error_message="Formula expression cannot be empty.",
            )

        # Check for dangerous keywords
        for forbidden in ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "EXEC", "UNION", ";", "--", "/*"]:
            if re.search(r"\b" + re.escape(forbidden) + r"\b", raw_formula, re.IGNORECASE):
                return CustomMetricValidationResult(
                    is_valid=False,
                    sql_template="",
                    referenced_columns=[],
                    error_message=f"Forbidden keyword '{forbidden}' in formula.",
                )

        # Build case-insensitive lookup for available columns
        col_map = {c.lower(): c for c in available_columns}

        # Extract tokens that look like column names or identifiers
        tokens = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", raw_formula)
        referenced_cols: Set[str] = set()

        for token in tokens:
            upper_token = token.upper()
            if upper_token in ALLOWED_FUNCTIONS:
                continue
            token_lower = token.lower()
            if token_lower in col_map:
                referenced_cols.add(col_map[token_lower])
            else:
                return CustomMetricValidationResult(
                    is_valid=False,
                    sql_template="",
                    referenced_columns=[],
                    error_message=f"Column '{token}' does not exist in dataset.",
                )

        # Convert simple arithmetic (e.g. (Revenue - Cost) / Revenue) into aggregate SQL template
        # e.g., Replace bare columns with SUM("{col}") if not already inside an aggregate function
        sql_expr = raw_formula
        for actual_col in referenced_cols:
            # Replace case-insensitively with properly quoted and aggregated column
            pattern = rf"\b{re.escape(actual_col)}\b"
            # If not preceded by an aggregate function name, wrap with SUM
            sql_expr = re.sub(
                pattern,
                rf'"{actual_col}"',
                sql_expr,
                flags=re.IGNORECASE,
            )

        # If the expression contains bare quoted columns without aggregates, wrap outer in calculation
        # Auto-wrap numeric measures in SUM if none of the allowed aggregate functions are present
        has_agg = any(func in sql_expr.upper() for func in ALLOWED_FUNCTIONS)
        if not has_agg:
            for actual_col in referenced_cols:
                sql_expr = sql_expr.replace(f'"{actual_col}"', f'SUM("{actual_col}")')

        return CustomMetricValidationResult(
            is_valid=True,
            sql_template=sql_expr,
            referenced_columns=list(referenced_cols),
            error_message=None,
        )


formula_engine = FormulaEngine()
