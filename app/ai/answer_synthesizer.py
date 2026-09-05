import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.ai.provider import BaseLLMProvider, get_llm_provider
from app.schemas.ai_dataset import AIDatasetUnderstanding
from app.schemas.chat import AnalyticalQueryPlan
from app.schemas.semantic import SemanticModelSchema

logger = logging.getLogger(__name__)


# Domain-aware example questions used when the AI has not yet produced
# per-dataset candidate questions. Keyed by the inferred business domain.
DOMAIN_EXAMPLE_QUESTIONS: Dict[str, List[str]] = {
    "human_resources": [
        "What is our total headcount by department?",
        "What is the average salary across job titles?",
        "Which departments have the highest turnover?",
    ],
    "sales": [
        "What is our total revenue?",
        "Show sales by country",
        "Which categories have the highest profit?",
    ],
    "ecommerce_sales": [
        "What is our total revenue and net profit?",
        "What are our top 5 products by sales?",
        "How has monthly revenue trended over time?",
    ],
    "retail_sales": [
        "What is our total revenue?",
        "Show sales by region",
        "Which categories have the highest profit?",
    ],
    "saas_subscription": [
        "What is our total MRR?",
        "What is our churn rate by subscription plan?",
        "How has monthly recurring revenue trended?",
    ],
    "logistics_supply_chain": [
        "What is our total shipment volume?",
        "Which carrier has the highest delivery volume?",
        "What is the average shipment weight?",
    ],
    "healthcare": [
        "How many patients are in the dataset?",
        "What are the most common diagnoses?",
        "Show patient volume over time.",
    ],
    "inventory": [
        "How many distinct products do we carry?",
        "Show stock distribution by category.",
        "Which products sell the highest volume?",
    ],
    "financial_transactions": [
        "What is our total transaction volume?",
        "Show transaction volume by region.",
        "How has daily transaction volume trended?",
    ],
    "generic_analytics": [
        "What is the total record count?",
        "Show the distribution of the main category.",
        "What are the top values by count?",
    ],
}

GREETINGS = {"hey", "hello", "hi", "hey!", "hello!", "hi!", "help", "who are you"}


class SynthesisResult(BaseModel):
    answer_text: str = Field(..., description="Executive narrative answering the user question")
    insights: List[str] = Field(default_factory=list, description="2-3 key analytical bullet insights")
    suggested_followups: List[str] = Field(default_factory=list, description="3 logical follow-up questions")


class AnswerSynthesizerAgent:
    """
    Synthesizes raw analytical query results into human-friendly executive answers,
    insights, and follow-up recommendations.
    """

    @classmethod
    def get_fallback_synthesis(
        cls,
        user_query: str,
        query_plan: AnalyticalQueryPlan,
        data_rows: List[Dict[str, Any]],
        semantic_model: Optional[SemanticModelSchema] = None,
    ) -> SynthesisResult:
        """
        Deterministic fallback synthesizer for offline or test environments.
        """
        q_lower = user_query.lower().strip()
        if q_lower in GREETINGS:
            domain = (semantic_model.domain or "generic_analytics") if semantic_model else "generic_analytics"
            example_questions = DOMAIN_EXAMPLE_QUESTIONS.get(domain, DOMAIN_EXAMPLE_QUESTIONS["generic_analytics"])
            examples_str = ", ".join(f"*{q}*" for q in example_questions)
            return SynthesisResult(
                answer_text=(
                    f"👋 Hello! I am your AI Business Intelligence Analyst. "
                    f"This is a **{domain.replace('_', ' ')}** dataset — "
                    f"ask me anything in plain English, for example: {examples_str}."
                ),
                insights=["You can ask analytical questions in plain English or click the suggested question chips below."],
                suggested_followups=example_questions,
            )

        if not data_rows:
            domain = (semantic_model.domain or "generic_analytics") if semantic_model else "generic_analytics"
            fallback_questions = DOMAIN_EXAMPLE_QUESTIONS.get(domain, DOMAIN_EXAMPLE_QUESTIONS["generic_analytics"])
            return SynthesisResult(
                answer_text="No matching records were found for your query criteria.",
                insights=["Consider broadening the filter parameters or verifying column values."],
                suggested_followups=fallback_questions,
            )

        if len(data_rows) == 1 and len(data_rows[0]) == 1:
            key, val = list(data_rows[0].items())[0]
            val_str = f"${val:,.2f}" if "rev" in key or "price" in key or "cost" in key or "profit" in key else f"{val:,}" if isinstance(val, (int, float)) else str(val)
            answer = f"The calculated **{key.replace('_', ' ').title()}** is **{val_str}**."
            domain = (semantic_model.domain or "generic_analytics") if semantic_model else "generic_analytics"
            fallback_questions = DOMAIN_EXAMPLE_QUESTIONS.get(domain, DOMAIN_EXAMPLE_QUESTIONS["generic_analytics"])
            return SynthesisResult(
                answer_text=answer,
                insights=[f"Total aggregation across the dataset yielded {val_str}."],
                suggested_followups=[
                    f"How does {key.replace('_', ' ')} break down by {query_plan.target_dimension or 'segment'}?",
                    f"What is the monthly trend for {key.replace('_', ' ')}?",
                    *fallback_questions[:1],
                ],
            )

        # Multi-row ranking or breakdown
        keys = list(data_rows[0].keys())
        dim_target = query_plan.target_dimension or ""
        
        # Match dimension key case-insensitively
        dim_col = None
        for k in keys:
            if dim_target and k.lower() == dim_target.lower():
                dim_col = k
                break
        if not dim_col:
            dim_col = keys[0]

        metric_cols = [k for k in keys if k != dim_col]
        primary_metric = metric_cols[0] if metric_cols else keys[0]

        # Distinct list / Exploratory question
        if query_plan.intent == "list_distinct" or any(w in user_query.lower() for w in ["which", "what", "list"]) and any(w in user_query.lower() for w in ["country", "countries", "region", "category", "product"]):
            dim_values = [str(r.get(dim_col) or r.get("dimension_value", "")) for r in data_rows if r.get(dim_col) or r.get("dimension_value")]
            dim_values_str = ", ".join(f"**{v}**" for v in dim_values[:10])
            count_suffix = f" (and {len(dim_values) - 10} more)" if len(dim_values) > 10 else ""
            
            answer = f"The dataset includes **{len(dim_values)} {dim_col.replace('_', ' ')} segments**: {dim_values_str}{count_suffix}."
            insights = [
                f"**{dim_values[0] if dim_values else 'Top segment'}** has the highest activity in the dataset.",
                f"Total of {len(dim_values)} unique {dim_col} values identified.",
            ]
            followups = [
                f"What is the total revenue for {dim_values[0] if dim_values else 'top segment'}?",
                f"Compare sales performance across these {dim_col} values.",
                f"What is the monthly trend by {dim_col}?",
            ]
            return SynthesisResult(
                answer_text=answer,
                insights=insights,
                suggested_followups=followups,
            )

        top_row = data_rows[0]
        top_name = str(top_row.get(dim_col) or "Top Leader")
        top_val = top_row.get(primary_metric, 0)
        top_val_str = f"${top_val:,.2f}" if isinstance(top_val, (int, float)) and any(w in primary_metric.lower() for w in ["rev", "price", "cost", "profit"]) else f"{top_val:,}" if isinstance(top_val, (int, float)) else str(top_val)

        # Use better phrasing for "highest" / "top" questions so the narrative
        # makes sense regardless of the underlying metric.
        is_top_n_question = any(w in user_query.lower() for w in ("top", "highest", "best", "leading"))
        if is_top_n_question:
            answer = (
                f"**{top_name}** leads with **{top_val_str}** "
                f"({primary_metric.replace('_', ' ')}), ranked across **{len(data_rows)} {dim_col.replace('_', ' ')}** groups."
            )
        else:
            answer = f"Analysis returned **{len(data_rows)} groups**. The highest performance is led by **{top_name}** with a {primary_metric.replace('_', ' ')} of **{top_val_str}**."

        insights = [
            f"**{top_name}** is the leading {dim_col.replace('_', ' ')} segment by {primary_metric.replace('_', ' ')}.",
            f"Values range from {top_val_str} (top) to {data_rows[-1].get(primary_metric, '—') if data_rows else '—'} across {len(data_rows)} groups.",
        ]

        followups = [
            f"What drove the high performance of {top_name}?",
            f"How does {dim_col} perform over time?",
            f"Show the bottom 5 {dim_col} by {primary_metric.replace('_', ' ')}.",
        ]

        return SynthesisResult(
            answer_text=answer,
            insights=insights,
            suggested_followups=followups,
        )

    @classmethod
    async def synthesize_answer(
        cls,
        user_query: str,
        query_plan: AnalyticalQueryPlan,
        data_rows: List[Dict[str, Any]],
        semantic_model: SemanticModelSchema,
        ai_understanding: Optional[AIDatasetUnderstanding] = None,
        provider: Optional[BaseLLMProvider] = None,
    ) -> SynthesisResult:
        """
        Generates executive commentary, derived bullet insights, and follow-ups from raw query results.
        """
        if not data_rows or user_query.lower().strip() in ["hey", "hello", "hi", "help"]:
            return cls.get_fallback_synthesis(user_query, query_plan, data_rows, semantic_model=semantic_model)

        llm = provider or get_llm_provider()

        prompt = f"""
User Question: "{user_query}"
Analytical Thought Process: {query_plan.thought_process}
SQL Query Executed: {query_plan.sql_query}

Raw Query Data (first 10 rows):
{data_rows[:10]}

Domain Context: {semantic_model.domain}
Business Summary: {ai_understanding.business_summary if ai_understanding else 'N/A'}

Provide an executive, concise business explanation of these numbers with 2-3 actionable insights and 3 logical follow-up questions.
"""

        system_prompt = """You are an executive AI Data Analyst.
Explain the validated numbers clearly, concisely, and accurately without hallucinating or inventing figures.
Highlight the primary answer directly, followed by concise actionable insights."""

        try:
            result: SynthesisResult = await llm.generate_structured(
                prompt=prompt,
                system_prompt=system_prompt,
                response_schema=SynthesisResult,
            )
            if result.answer_text and result.answer_text.strip():
                return result
        except Exception as exc:
            logger.warning("AI Answer synthesis failed: %s. Using deterministic fallback.", exc)

        return cls.get_fallback_synthesis(user_query, query_plan, data_rows, semantic_model=semantic_model)


answer_synthesizer_agent = AnswerSynthesizerAgent()
