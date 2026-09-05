import logging
import time
import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.answer_synthesizer import answer_synthesizer_agent
from app.ai.provider import BaseLLMProvider
from app.ai.query_guardrails import query_guardrail
from app.ai.query_translator import text_to_query_agent
from app.analytics.duckdb_engine import duckdb_engine
from app.repositories.chat_repository import ChatRepository
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.chat import (
    ChatMessage,
    ChatQueryRequest,
    ChatQueryResponse,
    ChatRole,
    SuggestedQuestionsResponse,
)
from app.schemas.semantic import BusinessConcept
from app.services.ai_dataset_service import AIDatasetService
from app.services.analytics_service import AnalyticsService
from app.services.profiler_service import ProfilerService
from app.services.semantic_service import SemanticService

logger = logging.getLogger(__name__)


def generate_query_id() -> str:
    return f"qry_{uuid.uuid4().hex[:12]}"


class ChatAnalystService:
    """
    End-to-end service coordinating natural language translation, security guardrails,
    DuckDB analytical execution, AI answer synthesis, and multi-turn session persistence.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.chat_repo = ChatRepository(db)
        self.profiler_service = ProfilerService(db)
        self.semantic_service = SemanticService(db)
        self.ai_service = AIDatasetService(db)
        self.analytics_service = AnalyticsService(db)

    async def _get_dataset_context(self, dataset_id: str):
        dataset = await self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset '{dataset_id}' not found.",
            )

        parquet_path = dataset.clean_file_path or dataset.file_path
        if not parquet_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dataset '{dataset_id}' has not been normalized into clean analytical format.",
            )

        profile = await self.profiler_service.get_dataset_profile(dataset_id)
        semantic_model = await self.semantic_service.get_semantic_model(dataset_id)
        available_metrics = await self.analytics_service.get_available_metrics(dataset_id)
        try:
            ai_understanding = await self.ai_service.get_understanding(dataset_id)
        except Exception:
            ai_understanding = None

        columns = [c.name for c in profile.columns_info]
        column_types = {c.name: c.detected_type.value for c in profile.columns_info}
        sample_values = {c.name: c.sample_values for c in profile.columns_info}

        return (
            dataset,
            parquet_path,
            columns,
            column_types,
            sample_values,
            semantic_model,
            available_metrics,
            ai_understanding,
        )

    async def ask_question(
        self,
        dataset_id: str,
        request: ChatQueryRequest,
        provider: Optional[BaseLLMProvider] = None,
    ) -> ChatQueryResponse:
        """
        Executes a natural-language business query against the dataset with full validation,
        AI synthesis, and persistent message logging.
        """
        start_time = time.perf_counter()
        query_id = generate_query_id()

        (
            _,
            parquet_path,
            columns,
            column_types,
            sample_values,
            semantic_model,
            available_metrics,
            ai_understanding,
        ) = await self._get_dataset_context(dataset_id)

        # 1. Fetch default persistent session
        session = await self.chat_repo.get_or_create_default_session(dataset_id)

        # 2. Append user message to database
        await self.chat_repo.add_message(
            session_id=session.id,
            role=ChatRole.USER.value,
            content=request.query,
        )

        # 3. Translate question to SQL query plan
        plan = await text_to_query_agent.translate_question(
            user_query=request.query,
            columns=columns,
            column_types=column_types,
            semantic_model=semantic_model,
            available_metrics=available_metrics,
            sample_values=sample_values,
            conversation_history=request.conversation_history,
            provider=provider,
        )

        # A syntactically valid query can still target an unavailable metric or
        # dimension. Replace semantically invalid LLM plans before execution.
        available_metric_ids = {metric.id for metric in available_metrics}
        valid_dimensions = set(columns)
        if (
            plan.target_metric
            and plan.target_metric not in available_metric_ids
        ) or (
            plan.target_dimension
            and plan.target_dimension not in valid_dimensions
        ):
            plan = text_to_query_agent.get_fallback_query_plan(
                user_query=request.query,
                columns=columns,
                semantic_model=semantic_model,
                available_metrics=available_metrics,
                conversation_history=request.conversation_history,
                sample_values=sample_values,
            )

        # 4. Guardrails validation and path rewrite
        is_valid, executable_sql, err_msg = query_guardrail.validate_and_rewrite_sql(
            raw_sql=plan.sql_query,
            parquet_path=parquet_path,
            valid_columns=columns,
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Query safety validation error: {err_msg}",
            )

        # 5. Execute query in DuckDB
        query_res = duckdb_engine.execute_safe_query(parquet_path=parquet_path, sql=executable_sql)
        raw_data = query_res.rows

        # 6. Synthesize executive answer & insights
        synthesis = await answer_synthesizer_agent.synthesize_answer(
            user_query=request.query,
            query_plan=plan,
            data_rows=raw_data,
            semantic_model=semantic_model,
            ai_understanding=ai_understanding,
            provider=provider,
        )

        # 7. Append assistant response to persistent session
        await self.chat_repo.add_message(
            session_id=session.id,
            role=ChatRole.ASSISTANT.value,
            content=synthesis.answer_text,
            sql_query=plan.sql_query,
            chart_type=plan.recommended_chart_type,
            data=raw_data,
        )

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return ChatQueryResponse(
            query_id=query_id,
            question=request.query,
            answer_text=synthesis.answer_text,
            insights=synthesis.insights,
            sql_query=plan.sql_query,
            data=raw_data,
            chart_type=plan.recommended_chart_type,
            suggested_followups=synthesis.suggested_followups,
            execution_time_ms=elapsed_ms,
        )

    async def get_suggested_questions(self, dataset_id: str) -> SuggestedQuestionsResponse:
        """
        Generates contextual suggested analytical questions for a dataset.
        """
        _, _, columns, _, _, semantic_model, available_metrics, ai_understanding = await self._get_dataset_context(dataset_id)

        available_ids = {m.id for m in available_metrics}
        domain = semantic_model.domain or "generic_analytics"
        date_col = semantic_model.date_column
        mappings = semantic_model.mappings or {}
        column_names_lower = {c.lower() for c in columns}

        dept_col = mappings.get(BusinessConcept.DEPARTMENT)
        job_col = mappings.get(BusinessConcept.JOB_TITLE)
        plan_col = mappings.get(BusinessConcept.SUBSCRIPTION_PLAN)
        carrier_col = mappings.get(BusinessConcept.CARRIER)
        diagnosis_col = mappings.get(BusinessConcept.DIAGNOSIS)

        # Resilience layer: if the semantic model misclassified the domain,
        # detect the *true* domain from the actual column names.
        has_dept_column = any(
            kw in " ".join(columns).lower()
            for kw in ("department", "dept")
        )
        has_salary_column = any(
            kw in " ".join(columns).lower()
            for kw in ("salary", "compensation", "wage")
        )
        has_employee_id_column = any(
            kw in " ".join(columns).lower()
            for kw in ("employeeid", "employee_id", "emp_id", "staff_id")
        )
        looks_like_hr = (
            domain == "human_resources"
            or "total_employees" in available_ids
            or (has_dept_column and (has_salary_column or has_employee_id_column))
        )
        has_subscription_col = any(kw in column_names_lower for kw in ("plan", "tier", "subscription"))
        has_mrr_col = any(kw in " ".join(columns).lower() for kw in ("mrr", "recurring_revenue", "monthly_recurring"))
        looks_like_saas = (
            domain == "saas_subscription" or "total_mrr" in available_ids or (has_subscription_col and has_mrr_col)
        )
        has_carrier_col = any(kw in column_names_lower for kw in ("carrier", "courier"))
        has_shipment_col = any(kw in column_names_lower for kw in ("shipment", "tracking"))
        looks_like_logistics = (
            domain == "logistics_supply_chain" or "total_shipments" in available_ids or (has_carrier_col or has_shipment_col)
        )
        has_diagnosis_col = any(kw in column_names_lower for kw in ("diagnosis", "disease", "icd"))
        has_patient_col = any(kw in column_names_lower for kw in ("patientid", "patient_id", "mrn"))
        looks_like_healthcare = (
            domain == "healthcare" or "total_patients" in available_ids or (has_diagnosis_col or has_patient_col)
        )

        # Dimension candidates, in priority order
        dim = (
            semantic_model.category_column
            or semantic_model.product_column
            or dept_col
            or job_col
            or plan_col
            or (semantic_model.dimensions[0] if semantic_model.dimensions else None)
        )

        # ----------------------------------------------------------------
        # Sales / revenue domain
        # ----------------------------------------------------------------
        if "total_revenue" in available_ids:
            questions = ["What is our total revenue and net profit?"]
            if dim:
                questions.append(f"What are our top 5 {dim}s by revenue?")
            if date_col:
                questions.append("How has monthly revenue trended over time?")
            if "profit_margin" in available_ids:
                questions.append("Which segments have the highest profit margin?")
            return SuggestedQuestionsResponse(dataset_id=dataset_id, questions=questions[:4])

        # ----------------------------------------------------------------
        # HR / workforce domain
        # ----------------------------------------------------------------
        if looks_like_hr:
            questions = ["What is our total headcount?"]
            if dept_col:
                questions.append("What is our headcount by department?")
            if "average_salary" in available_ids:
                questions.append("What is the average salary by department?")
            if job_col:
                questions.append("What are our top 5 job titles by count?")
            if date_col:
                questions.append("How has monthly headcount trended over time?")
            # Only use AI-understanding questions if we still have < 4 and they
            # do not contradict the detected domain (heuristic guard).
            if ai_understanding and len(questions) < 4:
                for q in ai_understanding.candidate_business_questions or []:
                    if any(bad in q.lower() for bad in ("revenue", "profit", "margin", "aov", "discount")):
                        continue
                    questions.append(q)
                    if len(questions) >= 4:
                        break
            return SuggestedQuestionsResponse(dataset_id=dataset_id, questions=questions[:4])

        # ----------------------------------------------------------------
        # SaaS domain
        # ----------------------------------------------------------------
        if looks_like_saas:
            questions = ["What is our total MRR?"]
            if plan_col:
                questions.append("What is the MRR by subscription plan?")
            if "churn_rate" in available_ids:
                questions.append("What is our churn rate by plan?")
            if date_col:
                questions.append("How has MRR trended over time?")
            return SuggestedQuestionsResponse(dataset_id=dataset_id, questions=questions[:4])

        # ----------------------------------------------------------------
        # Logistics domain
        # ----------------------------------------------------------------
        if looks_like_logistics:
            questions = ["What is our total shipment volume?"]
            if carrier_col:
                questions.append("Which carrier handles the most shipments?")
            if "average_weight" in available_ids:
                questions.append("What is the average shipment weight?")
            return SuggestedQuestionsResponse(dataset_id=dataset_id, questions=questions[:4])

        # ----------------------------------------------------------------
        # Healthcare domain
        # ----------------------------------------------------------------
        if looks_like_healthcare:
            questions = ["How many patients are in the dataset?"]
            if diagnosis_col:
                questions.append("What are the most common diagnoses?")
            if date_col:
                questions.append("Show patient volume over time.")
            return SuggestedQuestionsResponse(dataset_id=dataset_id, questions=questions[:4])

        # ----------------------------------------------------------------
        # Units / quantity domain (generic fallback before record count)
        # ----------------------------------------------------------------
        if "units_sold" in available_ids:
            questions = ["What is the total quantity of units sold?"]
            if dim:
                questions.append(f"Which {dim} has the highest volume?")
            if date_col:
                questions.append("How has unit volume trended over time?")
            return SuggestedQuestionsResponse(dataset_id=dataset_id, questions=questions[:4])

        # ----------------------------------------------------------------
        # Final generic fallback
        # ----------------------------------------------------------------
        questions = [
            "What is the total record count?",
            f"Show distribution of {dim or 'categories'}.",
        ]
        if date_col:
            questions.append("How has the record count trended over time?")
        if ai_understanding and len(questions) < 4:
            for q in ai_understanding.candidate_business_questions or []:
                ql = q.lower()
                # Drop questions that reference sales-economics concepts
                # unless those concepts actually exist in this dataset.
                if "revenue" in ql and "total_revenue" not in available_ids:
                    continue
                if "profit" in ql and "total_profit" not in available_ids:
                    continue
                if "margin" in ql and "profit_margin" not in available_ids:
                    continue
                if "discount" in ql and "discount_rate" not in available_ids:
                    continue
                questions.append(q)
                if len(questions) >= 4:
                    break
        return SuggestedQuestionsResponse(dataset_id=dataset_id, questions=questions[:4])

    async def list_sessions(self, dataset_id: str):
        return await self.chat_repo.list_sessions(dataset_id)

    async def get_session_messages(self, session_id: str):
        return await self.chat_repo.get_messages(session_id)
