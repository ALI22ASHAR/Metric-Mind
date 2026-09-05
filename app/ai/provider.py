from abc import ABC, abstractmethod
import json
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel

from app.core.config import Settings, settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseLLMProvider(ABC):
    """
    Abstract interface for LLM operations supporting structured JSON schema extraction.
    """

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str,
        response_schema: Type[T],
    ) -> T:
        """
        Generates a validated structured response matching the specified Pydantic schema.
        """
        pass

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: str,
    ) -> str:
        """
        Generates freeform text.
        """
        pass


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic Mock LLM Provider for offline development and hermetic unit/integration tests.
    Extracts column knowledge directly from the prompt to formulate intelligent, structured responses.
    """

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str,
        response_schema: Type[T],
    ) -> T:
        logger.info("MockLLMProvider invoked for structured generation (%s)", response_schema.__name__)

        # Extract available columns from prompt if present
        cols_lower = prompt.lower()

        # Build dynamic mock responses based on schema type
        if response_schema.__name__ == "AIDatasetUnderstanding":
            # Extract dataset_id and inferred domain from prompt
            dataset_id = "ds_mock"
            inferred_domain = None
            for line in prompt.splitlines():
                if "dataset id:" in line.lower():
                    dataset_id = line.split(":")[-1].strip()
                if "current inferred domain:" in line.lower():
                    inferred_domain = line.split(":")[-1].strip().lower()

            # Dynamic domain deduction
            if inferred_domain and inferred_domain != "generic_business":
                domain = inferred_domain
            elif any(k in cols_lower for k in ["employee_id", "department", "hire_date", "salary", "job_title"]):
                domain = "human_resources"
            elif any(k in cols_lower for k in ["user_id", "mrr", "subscription", "plan", "churn"]):
                domain = "saas_subscription"
            elif any(k in cols_lower for k in ["shipment_id", "carrier", "tracking_number", "weight"]):
                domain = "logistics_supply_chain"
            elif any(k in cols_lower for k in ["patient_id", "diagnosis", "doctor", "admission_date"]):
                domain = "healthcare"
            elif any(k in cols_lower for k in ["order_id", "sale_price", "revenue", "product", "quantity"]):
                domain = "sales"
            else:
                domain = "generic_analytics"

            # Dynamic hierarchies
            hierarchies: List[List[str]] = []
            if "country" in cols_lower and "city" in cols_lower:
                if "state" in cols_lower:
                    hierarchies.append(["country", "state", "city"])
                else:
                    hierarchies.append(["country", "city"])
            elif "region" in cols_lower:
                hierarchies.append(["region"])

            if "department" in cols_lower and "job_title" in cols_lower:
                hierarchies.append(["department", "job_title"])
            elif "category" in cols_lower and ("product" in cols_lower or "item" in cols_lower):
                prod_col = "product" if "product" in cols_lower else "item"
                hierarchies.append(["category", prod_col])

            # Dynamic date column
            date_col = None
            for d in ["hire_date", "join_date", "start_date", "order_date", "trans_date", "date", "created_at"]:
                if d in cols_lower:
                    date_col = d
                    break

            # Refined mappings
            mappings: Dict[str, str] = {}
            if "employee_id" in cols_lower:
                mappings["employee_id_column"] = "employee_id"
            if "department" in cols_lower:
                mappings["department_column"] = "department"
            if "job_title" in cols_lower:
                mappings["job_title_column"] = "job_title"
            if "salary" in cols_lower:
                mappings["salary_column"] = "salary"
            elif "annual_salary" in cols_lower:
                mappings["salary_column"] = "annual_salary"
            if "order_id" in cols_lower:
                mappings["order_id_column"] = "order_id"
            if date_col:
                mappings["date_column"] = date_col
                if date_col in {"hire_date", "join_date", "start_date"}:
                    mappings["hire_date_column"] = date_col
            if "product" in cols_lower:
                mappings["product_column"] = "product"
            elif "item" in cols_lower:
                mappings["product_column"] = "item"
            if "category" in cols_lower:
                mappings["category_column"] = "category"
            if "quantity" in cols_lower:
                mappings["quantity_column"] = "quantity"
            elif "qty" in cols_lower:
                mappings["quantity_column"] = "qty"
            if "sale_price" in cols_lower:
                mappings["sale_price_column"] = "sale_price"
            elif "sp" in cols_lower:
                mappings["sale_price_column"] = "sp"
            if "cost_price" in cols_lower:
                mappings["cost_price_column"] = "cost_price"
            elif "cp" in cols_lower:
                mappings["cost_price_column"] = "cp"

            # Domain-tailored summaries and recommendations
            if domain == "human_resources":
                summary = "This dataset tracks employee records, departmental headcount, job roles, compensation, and organizational workforce metrics."
                rec_metrics = ["total_employees", "active_departments", "workforce_locations", "average_salary", "average_age"]
                rec_questions = [
                    "What is the total employee headcount across departments?",
                    "Which departments have the largest workforce?",
                    "What is our hiring trajectory and headcount growth over time?",
                    "How is employee talent distributed across geographic cities?",
                ]
            elif domain == "saas_subscription":
                summary = "This dataset tracks active subscribers, monthly recurring revenue (MRR), subscription tiers, and customer retention."
                rec_metrics = ["total_users", "total_mrr", "active_plans"]
                rec_questions = [
                    "What is our total Monthly Recurring Revenue (MRR)?",
                    "Which subscription plan tier has the most subscribers?",
                    "What is our subscriber growth rate over time?",
                ]
            elif domain == "logistics_supply_chain":
                summary = "This dataset tracks shipment fulfillment, freight carriers, delivery routes, and logistical throughput."
                rec_metrics = ["total_shipments", "active_carriers", "average_weight"]
                rec_questions = [
                    "What is our total shipment volume?",
                    "Which carrier handles the largest share of deliveries?",
                ]
            elif domain == "sales":
                summary = "This dataset tracks commercial sales transactions, customer orders, product pricing, and gross revenue performance."
                rec_metrics = ["total_revenue", "total_profit", "gross_margin_percentage", "total_orders", "average_order_value"]
                rec_questions = [
                    "What is our total revenue and gross profit margin?",
                    "Which product categories generate the highest margin?",
                    "How do sales compare across regions over time?",
                    "Who are our top performing sales regions?",
                ]
            else:
                summary = "This dataset contains multi-dimensional operational records, category segments, and statistical distributions."
                rec_metrics = ["total_records"]
                rec_questions = [
                    "What is the total volume of records in this dataset?",
                    "How are records distributed across major dimensions?",
                ]

            mock_payload = {
                "dataset_id": dataset_id,
                "domain": domain,
                "business_summary": summary,
                "primary_date_column": date_col,
                "refined_mappings": mappings,
                "dimension_hierarchies": hierarchies,
                "recommended_metrics": rec_metrics,
                "candidate_business_questions": rec_questions,
                "confidence_score": 0.96,
            }
            return response_schema.model_validate(mock_payload)

        # Fallback empty model
        return response_schema.model_validate({"dataset_id": "ds_mock"})

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str,
    ) -> str:
        logger.info("MockLLMProvider invoked for text generation")
        return "Analysis complete. The dataset exhibits healthy sales activity with distinct dimensional segments."


class OpenAILLMProvider(BaseLLMProvider):
    """
    OpenAI LLM Provider using official OpenAI structured JSON outputs.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key
        self.model = model

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str,
        response_schema: Type[T],
    ) -> T:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)
            response = await client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                response_format=response_schema,
            )
            return response.choices[0].message.parsed
        except Exception as exc:
            logger.error("OpenAI structured request failed: %s. Falling back to MockLLMProvider", exc)
            return await MockLLMProvider().generate_structured(prompt, system_prompt, response_schema)

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str,
    ) -> str:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("OpenAI text request failed: %s", exc)
            return await MockLLMProvider().generate_text(prompt, system_prompt)


class NVIDIADeepSeekProvider(BaseLLMProvider):
    """NVIDIA NIM provider using its OpenAI-compatible chat completions API."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    async def generate_structured(self, prompt: str, system_prompt: str, response_schema: Type[T]) -> T:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                temperature=0.0,
                top_p=0.95,
                max_tokens=16384,
                response_format={"type": "json_object"},
                extra_body={"chat_template_kwargs": {"thinking": False}},
            )
            return response_schema.model_validate_json(response.choices[0].message.content or "{}")
        except Exception as exc:
            logger.error("NVIDIA DeepSeek structured request failed: %s. Falling back to MockLLMProvider", exc)
            return await MockLLMProvider().generate_structured(prompt, system_prompt, response_schema)

    async def generate_text(self, prompt: str, system_prompt: str) -> str:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                temperature=0.2,
                top_p=0.95,
                max_tokens=16384,
                extra_body={"chat_template_kwargs": {"thinking": False}},
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("NVIDIA DeepSeek text request failed: %s", exc)
            return await MockLLMProvider().generate_text(prompt, system_prompt)


class GeminiLLMProvider(BaseLLMProvider):
    """
    Google Gemini Provider using structured output schema.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self.api_key = api_key
        self.model = model

    @staticmethod
    def _gemini_schema(response_schema: Type[T]) -> Dict[str, Any]:
        """Convert Pydantic JSON schema to the subset accepted by Gemini REST."""
        def normalize(value: Any) -> Any:
            if isinstance(value, dict):
                normalized = {}
                for key, item in value.items():
                    if key in {"title", "description", "default", "additionalProperties"}:
                        continue
                    target_key = {
                        "type": "type",
                        "properties": "properties",
                        "required": "required",
                        "items": "items",
                        "enum": "enum",
                    }.get(key, key)
                    normalized[target_key] = normalize(item)
                return normalized
            if isinstance(value, list):
                return [normalize(item) for item in value]
            return value

        return normalize(response_schema.model_json_schema())

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str,
        response_schema: Type[T],
    ) -> T:
        try:
            import httpx
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            payload = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": self._gemini_schema(response_schema),
                },
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return response_schema.model_validate_json(text)
        except Exception as exc:
            logger.error("Gemini structured request failed: %s. Falling back to MockLLMProvider", exc)
            return await MockLLMProvider().generate_structured(prompt, system_prompt, response_schema)

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str,
    ) -> str:
        try:
            import httpx
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            payload = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"parts": [{"text": prompt}]}],
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:
            logger.error("Gemini text request failed: %s", exc)
            return await MockLLMProvider().generate_text(prompt, system_prompt)


def get_llm_provider(custom_settings: Optional[Settings] = None) -> BaseLLMProvider:
    """
    Factory creating the configured LLM provider instance.
    """
    cfg = custom_settings or settings
    provider_name = (cfg.LLM_PROVIDER or "mock").lower().strip()

    if provider_name == "openai" and cfg.OPENAI_API_KEY:
        return OpenAILLMProvider(api_key=cfg.OPENAI_API_KEY, model=cfg.OPENAI_MODEL)
    elif provider_name == "gemini" and cfg.GEMINI_API_KEY:
        return GeminiLLMProvider(api_key=cfg.GEMINI_API_KEY, model=cfg.GEMINI_MODEL)
    elif provider_name in {"nvidia", "deepseek"} and cfg.NVIDIA_API_KEY:
        return NVIDIADeepSeekProvider(
            api_key=cfg.NVIDIA_API_KEY,
            base_url=cfg.NVIDIA_BASE_URL,
            model=cfg.NVIDIA_MODEL,
        )

    return MockLLMProvider()
