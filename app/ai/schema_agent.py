import logging
from typing import Dict, List, Optional
from app.ai.provider import BaseLLMProvider, get_llm_provider
from app.schemas.ai_dataset import AIDatasetUnderstanding
from app.schemas.profile import DatasetProfileResponse
from app.schemas.semantic import SemanticModelSchema

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Data Architect and Business Intelligence Analyst.
Your goal is to inspect the structural metadata, column types, statistical distributions, and sample values of an uploaded business dataset, then output a rich, accurate analytical understanding.

CRITICAL GUARDRAILS & RULES:
1. ANTI-HALLUCINATION: You MUST ONLY reference column names that exist in the provided schema. Do NOT invent, guess, or modify column names.
2. If an ambiguous column clearly represents a standard business concept (e.g. 'sp' -> 'sale_price_column'), include it in 'refined_mappings'.
3. Identify multi-level drill-down dimensional hierarchies (e.g. ['Country', 'State', 'City'] or ['Category', 'Product']).
4. Recommend actionable business questions and computable KPIs tailored specifically to the dataset.
"""


class SchemaUnderstandingAgent:
    """
    Agent responsible for analyzing dataset metadata, synthesizing domain understanding,
    and recommending analytical hierarchies and KPIs.
    """

    @classmethod
    def format_dataset_prompt(
        cls,
        dataset_id: str,
        profile: DatasetProfileResponse,
        semantic_model: SemanticModelSchema,
    ) -> str:
        """
        Creates a compact, privacy-safe metadata prompt containing column statistics and 3 sample values.
        """
        lines = [
            f"Dataset ID: {dataset_id}",
            f"Total Rows: {profile.summary.row_count}",
            f"Total Columns: {profile.summary.column_count}",
            f"Current Inferred Domain: {semantic_model.domain}",
            "",
            "=== COLUMN METADATA & SAMPLE VALUES ===",
        ]

        for col in profile.columns_info:
            samples_str = ", ".join([repr(s) for s in col.sample_values[:3]])
            lines.append(
                f"- Column '{col.name}': Type={col.detected_type.value}, Role={col.role.value}, "
                f"NullCount={col.null_count}, UniqueCount={col.unique_count}, Samples=[{samples_str}]"
            )

        lines.extend([
            "",
            "=== CURRENT HEURISTIC MAPPINGS ===",
        ])
        for concept, col_name in semantic_model.mappings.items():
            lines.append(f"- {concept}: '{col_name}'")

        lines.extend([
            "",
            "Analyze this dataset and produce the structured AIDatasetUnderstanding output.",
        ])

        return "\n".join(lines)

    @classmethod
    def sanitize_understanding(
        cls,
        understanding: AIDatasetUnderstanding,
        valid_columns: List[str],
    ) -> AIDatasetUnderstanding:
        """
        Sanitizes AI output to ensure no hallucinated column names are persisted,
        resolving case differences to match exact dataset column headers.
        """
        col_case_map: Dict[str, str] = {c.lower(): c for c in valid_columns}

        # 1. Filter and match primary date column
        if understanding.primary_date_column:
            matched_date = col_case_map.get(understanding.primary_date_column.lower())
            if matched_date:
                understanding.primary_date_column = matched_date
            else:
                logger.warning(
                    "Stripping invalid primary_date_column '%s' recommended by AI",
                    understanding.primary_date_column,
                )
                understanding.primary_date_column = None

        # 2. Filter and match refined mappings
        filtered_mappings = {}
        for concept, col_name in understanding.refined_mappings.items():
            matched_col = col_case_map.get(col_name.lower())
            if matched_col:
                filtered_mappings[concept] = matched_col
            else:
                logger.warning(
                    "Stripping hallucinated column '%s' for concept '%s' from AI mapping",
                    col_name,
                    concept,
                )
        understanding.refined_mappings = filtered_mappings

        # 3. Filter and match dimension hierarchies
        filtered_hierarchies = []
        for hierarchy in understanding.dimension_hierarchies:
            cleaned = []
            for c in hierarchy:
                matched = col_case_map.get(c.lower())
                if matched:
                    cleaned.append(matched)
            if len(cleaned) >= 1:
                filtered_hierarchies.append(cleaned)
        understanding.dimension_hierarchies = filtered_hierarchies

        return understanding

    @classmethod
    async def analyze_dataset(
        cls,
        dataset_id: str,
        profile: DatasetProfileResponse,
        semantic_model: SemanticModelSchema,
        provider: Optional[BaseLLMProvider] = None,
    ) -> AIDatasetUnderstanding:
        """
        Runs the AI dataset understanding workflow using the configured LLM provider.
        """
        llm = provider or get_llm_provider()
        prompt = cls.format_dataset_prompt(dataset_id, profile, semantic_model)

        raw_understanding: AIDatasetUnderstanding = await llm.generate_structured(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            response_schema=AIDatasetUnderstanding,
        )

        valid_columns = [col.name for col in profile.columns_info]
        sanitized = cls.sanitize_understanding(raw_understanding, valid_columns)
        sanitized.dataset_id = dataset_id

        return sanitized


schema_understanding_agent = SchemaUnderstandingAgent()
