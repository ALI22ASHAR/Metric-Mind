import re
from pathlib import Path
from typing import List, Tuple

FORBIDDEN_SQL_KEYWORDS = {
    "drop",
    "delete",
    "update",
    "insert",
    "alter",
    "attach",
    "copy",
    "vacuum",
    "load",
    "install",
    "create",
    "truncate",
    "grant",
    "revoke",
    "pragma",
}


class QueryGuardrail:
    """
    Security and validation layer for AI-generated SQL queries before DuckDB execution.
    """

    @classmethod
    def validate_and_rewrite_sql(
        cls,
        raw_sql: str,
        parquet_path: str,
        valid_columns: List[str],
    ) -> Tuple[bool, str, str]:
        """
        Validates safety, checks column existence, and rewrites the FROM clause to point to the parquet file.
        Returns: (is_valid: bool, executable_sql: str, error_message: str)
        """
        cleaned = raw_sql.strip()

        # 1. Check for starting SELECT / WITH
        normalized_upper = cleaned.upper()
        if not (normalized_upper.startswith("SELECT") or normalized_upper.startswith("WITH")):
            return False, "", "Only read-only SELECT queries are permitted."

        # 2. Check for forbidden keywords as standalone words
        for kw in FORBIDDEN_SQL_KEYWORDS:
            if re.search(rf"\b{kw}\b", cleaned, re.IGNORECASE):
                return False, "", f"Only read-only SELECT queries are permitted. Prohibited SQL operation detected: '{kw.upper()}'."

        # 3. Check for multiple semicolons (prevent multi-statement injections)
        statements = [s for s in cleaned.split(";") if s.strip()]
        if len(statements) > 1:
            return False, "", "Multiple SQL statements are not permitted."

        single_statement = statements[0].strip()

        # Reject identifiers that look like columns but are not in the profiled
        # dataset. SQL keywords, functions, aliases, and literals are excluded.
        identifier_pattern = re.compile(r'(?<![.\w])"?([A-Za-z_][A-Za-z0-9_]*)"?(?![.\w])')
        sql_keywords = {
            "select", "from", "where", "group", "by", "order", "limit", "asc", "desc",
            "as", "and", "or", "not", "null", "is", "in", "between", "case", "when",
            "then", "else", "end", "distinct", "join", "on", "left", "right", "inner",
            "outer", "having", "offset", "true", "false", "data",
        }
        sql_functions = {"count", "sum", "avg", "min", "max", "round", "strftime", "date_trunc", "nullif", "cast"}
        identifiers = {
            match.group(1)
            for match in identifier_pattern.finditer(single_statement)
            if match.group(1).lower() not in sql_keywords
            and match.group(1).lower() not in sql_functions
            and not match.group(1).isdigit()
        }
        allowed_identifiers = {column.lower() for column in valid_columns}
        aliases = {
            "month", "week", "quarter", "year", "day", "value", "count", "total_count",
            *{match.group(1).lower() for match in re.finditer(r"\bAS\s+\"?([A-Za-z_][A-Za-z0-9_]*)\"?", single_statement, re.IGNORECASE)},
        }
        unknown = sorted(identifier for identifier in identifiers if identifier.lower() not in allowed_identifiers and identifier.lower() not in aliases)
        if unknown:
            return False, "", f"Unknown dataset column(s): {', '.join(unknown)}."

        # 4. Rewrite 'data' table reference to parquet path
        posix_path = Path(parquet_path).as_posix()
        rewritten_sql = re.sub(
            r"\bFROM\s+['\"]?data['\"]?\b",
            f"FROM '{posix_path}'",
            single_statement,
            flags=re.IGNORECASE,
        )
        rewritten_sql = re.sub(
            r"\bJOIN\s+['\"]?data['\"]?\b",
            f"JOIN '{posix_path}'",
            rewritten_sql,
            flags=re.IGNORECASE,
        )

        # If no table reference was present, inject FROM parquet_path
        if f"'{posix_path}'" not in rewritten_sql:
            # Check if there is any other table name
            match = re.search(r"\bFROM\s+([a-zA-Z0-9_]+)", rewritten_sql, re.IGNORECASE)
            if match:
                old_table = match.group(1)
                rewritten_sql = re.sub(
                    rf"\bFROM\s+{old_table}\b",
                    f"FROM '{posix_path}'",
                    rewritten_sql,
                    flags=re.IGNORECASE,
                )
            else:
                return False, "", "SQL query must specify a FROM clause."

        return True, rewritten_sql, ""


query_guardrail = QueryGuardrail()
