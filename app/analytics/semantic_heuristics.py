from datetime import datetime, timezone
import re
from typing import Dict, List, Optional, Tuple
import polars as pl

from app.schemas.profile import ColumnProfile, ColumnRole, ColumnType
from app.schemas.semantic import BusinessConcept, SemanticModelSchema

# Concept synonym patterns with base confidence weights
CONCEPT_PATTERNS: Dict[str, List[Tuple[re.Pattern, float]]] = {
    BusinessConcept.DATE: [
        (re.compile(r"^(order_?date|trans_?date|transaction_?date|sale_?date|purchase_?date|invoice_?date)$", re.I), 0.98),
        (re.compile(r"^(date|created_?at|timestamp|event_?date|time|datetime)$", re.I), 0.90),
        (re.compile(r"(date|time|timestamp)", re.I), 0.75),
    ],
    BusinessConcept.QUANTITY: [
        (re.compile(r"^(quantity|qty|units_?sold|units|order_?qty|order_?quantity)$", re.I), 0.98),
        (re.compile(r"^(volume|items_?count|count|num_?items|pieces)$", re.I), 0.85),
        (re.compile(r"(quantity|qty|units)", re.I), 0.75),
    ],
    BusinessConcept.SALE_PRICE: [
        (re.compile(r"^(sale_?price|selling_?price|sp|unit_?price|retail_?price|item_?price|product_?price)$", re.I), 0.98),
        (re.compile(r"^(price|rate|unit_?rate)$", re.I), 0.88),
        (re.compile(r"(sale_?price|unit_?price|price)", re.I), 0.75),
    ],
    BusinessConcept.COST_PRICE: [
        (re.compile(r"^(cost_?price|unit_?cost|cp|cogs|base_?cost|purchase_?cost|item_?cost|unit_?cogs)$", re.I), 0.98),
        (re.compile(r"^(cost|expense|base_?price)$", re.I), 0.85),
        (re.compile(r"(cost_?price|unit_?cost|cogs|cost)", re.I), 0.75),
    ],
    BusinessConcept.REVENUE: [
        (re.compile(r"^(total_?revenue|revenue|total_?sales|gross_?sales|total_?amount|line_?total|subtotal)$", re.I), 0.98),
        (re.compile(r"^(sales|amount|turnover)$", re.I), 0.85),
    ],
    BusinessConcept.PROFIT: [
        (re.compile(r"^(total_?profit|profit|net_?profit|gross_?profit|earnings|net_?income)$", re.I), 0.98),
        (re.compile(r"^(margin)$", re.I), 0.80),
    ],
    BusinessConcept.PRODUCT: [
        (re.compile(r"^(product_?name|product_?title|item_?name|product|item|item_?desc|article)$", re.I), 0.98),
        (re.compile(r"^(description|title|goods)$", re.I), 0.80),
    ],
    BusinessConcept.PRODUCT_ID: [
        (re.compile(r"^(product_?id|sku|sku_?id|item_?id|item_?code|product_?code|asin)$", re.I), 0.98),
    ],
    BusinessConcept.CATEGORY: [
        (re.compile(r"^(product_?category|category|item_?category|sub_?category|dept|department|segment|product_?type|line)$", re.I), 0.98),
        (re.compile(r"^(type|group|class|family)$", re.I), 0.75),
    ],
    BusinessConcept.CUSTOMER: [
        (re.compile(r"^(customer_?name|client_?name|customer|client|buyer|account_?name)$", re.I), 0.98),
    ],
    BusinessConcept.CUSTOMER_ID: [
        (re.compile(r"^(customer_?id|client_?id|cust_?id|account_?id|user_?id|account_?number)$", re.I), 0.98),
    ],
    BusinessConcept.ORDER_ID: [
        (re.compile(r"^(order_?id|invoice_?id|invoice_?num|invoice_?number|transaction_?id|tx_?id|order_?number|order_?num)$", re.I), 0.98),
        (re.compile(r"^(id|order|invoice|txn_?id)$", re.I), 0.80),
    ],
    BusinessConcept.CITY: [
        (re.compile(r"^(city|town|municipality)$", re.I), 0.98),
    ],
    BusinessConcept.STATE: [
        (re.compile(r"^(state|province|prefecture|canton)$", re.I), 0.98),
    ],
    BusinessConcept.COUNTRY: [
        (re.compile(r"^(country|nation|country_?code|country_?name)$", re.I), 0.98),
    ],
    BusinessConcept.REGION: [
        (re.compile(r"^(region|territory|zone|area|continent|division|geo_?region)$", re.I), 0.98),
    ],
    BusinessConcept.DISCOUNT: [
        (re.compile(r"^(discount|discount_?amount|discount_?rate|discount_?pct|promo_?discount)$", re.I), 0.98),
    ],
    # HR & Workforce Patterns
    BusinessConcept.EMPLOYEE_ID: [
        (re.compile(r"^(employee_?id|emp_?id|staff_?id|worker_?id|badge_?num|person_?id)$", re.I), 0.98),
    ],
    BusinessConcept.EMPLOYEE_NAME: [
        (re.compile(r"^(employee_?name|emp_?name|staff_?name|worker_?name|full_?name|person_?name)$", re.I), 0.98),
        (re.compile(r"^(name|employee)$", re.I), 0.85),
    ],
    BusinessConcept.DEPARTMENT: [
        (re.compile(r"^(department|dept|business_?unit|division|team|group|org_?unit)$", re.I), 0.98),
    ],
    BusinessConcept.JOB_TITLE: [
        (re.compile(r"^(job_?title|title|role|position|designation|job_?role|occupation)$", re.I), 0.98),
    ],
    BusinessConcept.HIRE_DATE: [
        (re.compile(r"^(hire_?date|start_?date|join_?date|onboarding_?date|employment_?date)$", re.I), 0.98),
    ],
    BusinessConcept.SALARY: [
        (re.compile(r"^(salary|annual_?salary|monthly_?salary|compensation|base_?pay|wage|hourly_?rate)$", re.I), 0.98),
    ],
    BusinessConcept.AGE: [
        (re.compile(r"^(age|employee_?age|years_?old)$", re.I), 0.98),
    ],
    BusinessConcept.TENURE: [
        (re.compile(r"^(tenure|years_?of_?service|experience|years_?at_?company)$", re.I), 0.98),
    ],
    BusinessConcept.STATUS: [
        (re.compile(r"^(status|employment_?status|active_?status|is_?active|attrition|attrition_?status)$", re.I), 0.98),
    ],
    BusinessConcept.EDUCATION: [
        (re.compile(r"^(education|education_?level|degree|qualification)$", re.I), 0.98),
    ],
    BusinessConcept.PERFORMANCE_RATING: [
        (re.compile(r"^(performance_?rating|rating|score|review_?score|performance_?score)$", re.I), 0.98),
    ],
    BusinessConcept.GENDER: [
        (re.compile(r"^(gender|sex)$", re.I), 0.98),
    ],
    BusinessConcept.WORK_MODE: [
        (re.compile(r"^(work_?mode|workmode|remote_?status|employment_?type)$", re.I), 0.98),
    ],
    BusinessConcept.MARITAL_STATUS: [
        (re.compile(r"^(marital_?status|marital|relationship_?status)$", re.I), 0.98),
    ],
    BusinessConcept.SALARY_BAND: [
        (re.compile(r"^(salary_?band|pay_?band|comp_?band|grade)$", re.I), 0.98),
    ],
    # SaaS Patterns
    BusinessConcept.USER_ID: [
        (re.compile(r"^(user_?id|account_?id|subscriber_?id|member_?id)$", re.I), 0.98),
    ],
    BusinessConcept.SUBSCRIPTION_PLAN: [
        (re.compile(r"^(plan|tier|subscription_?plan|subscription_?tier|package)$", re.I), 0.98),
    ],
    BusinessConcept.MRR: [
        (re.compile(r"^(mrr|monthly_?recurring_?revenue|arr|annual_?recurring_?revenue)$", re.I), 0.98),
    ],
    BusinessConcept.CHURN: [
        (re.compile(r"^(churn|is_?churned|churn_?status|cancelled)$", re.I), 0.98),
    ],
    # Logistics Patterns
    BusinessConcept.SHIPMENT_ID: [
        (re.compile(r"^(shipment_?id|tracking_?number|tracking_?id|parcel_?id|package_?id)$", re.I), 0.98),
    ],
    BusinessConcept.CARRIER: [
        (re.compile(r"^(carrier|shipping_?carrier|courier|logistics_?partner|delivery_?method)$", re.I), 0.98),
    ],
    BusinessConcept.WEIGHT: [
        (re.compile(r"^(weight|package_?weight|gross_?weight|kg|lbs)$", re.I), 0.98),
    ],
    # Healthcare Patterns
    BusinessConcept.PATIENT_ID: [
        (re.compile(r"^(patient_?id|mrn|medical_?record_?number|subject_?id)$", re.I), 0.98),
    ],
    BusinessConcept.DIAGNOSIS: [
        (re.compile(r"^(diagnosis|disease|condition|icd_?code|medical_?condition)$", re.I), 0.98),
    ],
}


class SemanticModelBuilder:
    """
    Infers a validated semantic model from dataset columns and profiling metadata.
    """

    @classmethod
    def matches_concept(
        cls,
        concept: str,
        col_name: str,
        col_type: ColumnType,
        col_role: ColumnRole,
    ) -> Tuple[bool, float]:
        """
        Tests if a column name matches a business concept and satisfies type constraints.
        Returns (is_match, confidence_score).
        """
        numeric_concepts = {
            BusinessConcept.QUANTITY,
            BusinessConcept.SALE_PRICE,
            BusinessConcept.COST_PRICE,
            BusinessConcept.REVENUE,
            BusinessConcept.PROFIT,
            BusinessConcept.DISCOUNT,
            BusinessConcept.SALARY,
            BusinessConcept.AGE,
            BusinessConcept.TENURE,
            BusinessConcept.MRR,
            BusinessConcept.WEIGHT,
            BusinessConcept.PERFORMANCE_RATING,
        }
        if concept in numeric_concepts and col_type != ColumnType.NUMERIC:
            return False, 0.0

        date_concepts = {BusinessConcept.DATE, BusinessConcept.HIRE_DATE}
        if concept in date_concepts and col_type not in (ColumnType.DATE, ColumnType.DATETIME) and col_role != ColumnRole.TIME_DIMENSION:
            return False, 0.0

        clean_col = col_name.strip().lower()
        patterns = CONCEPT_PATTERNS.get(concept, [])

        for pattern, base_conf in patterns:
            if pattern.search(clean_col):
                # Adjust confidence based on column role compatibility
                role_boost = 0.0
                if col_role == ColumnRole.MEASURE and concept in numeric_concepts:
                    role_boost = 0.02
                elif col_role == ColumnRole.DIMENSION and concept not in numeric_concepts:
                    role_boost = 0.02
                elif col_role == ColumnRole.TIME_DIMENSION and concept in date_concepts:
                    role_boost = 0.02

                return True, min(1.0, base_conf + role_boost)

        return False, 0.0

    @classmethod
    def build_semantic_model(
        cls,
        dataset_id: str,
        columns_info: List[ColumnProfile],
    ) -> SemanticModelSchema:
        """
        Builds a complete SemanticModelSchema from columns profiling data.
        """
        mappings: Dict[str, str] = {}
        confidence_scores: Dict[str, float] = {}
        used_columns = set()

        dimensions: List[str] = []
        measures: List[str] = []
        time_dimensions: List[str] = []
        identifiers: List[str] = []

        cols_to_evaluate = list(columns_info)

        for col in columns_info:
            c_name = col.name
            if col.role == ColumnRole.ID:
                identifiers.append(c_name)
            elif col.role == ColumnRole.TIME_DIMENSION:
                time_dimensions.append(c_name)
            elif col.role == ColumnRole.MEASURE:
                measures.append(c_name)
            elif col.role == ColumnRole.DIMENSION:
                dimensions.append(c_name)

        # Match concepts in priority order
        concept_priority = [
            BusinessConcept.EMPLOYEE_ID,
            BusinessConcept.EMPLOYEE_NAME,
            BusinessConcept.DEPARTMENT,
            BusinessConcept.JOB_TITLE,
            BusinessConcept.HIRE_DATE,
            BusinessConcept.SALARY,
            BusinessConcept.SALARY_BAND,
            BusinessConcept.ORDER_ID,
            BusinessConcept.USER_ID,
            BusinessConcept.SHIPMENT_ID,
            BusinessConcept.PATIENT_ID,
            BusinessConcept.DATE,
            BusinessConcept.QUANTITY,
            BusinessConcept.SALE_PRICE,
            BusinessConcept.COST_PRICE,
            BusinessConcept.REVENUE,
            BusinessConcept.PROFIT,
            BusinessConcept.PRODUCT,
            BusinessConcept.CATEGORY,
            BusinessConcept.CUSTOMER,
            BusinessConcept.CITY,
            BusinessConcept.STATE,
            BusinessConcept.COUNTRY,
            BusinessConcept.REGION,
            BusinessConcept.DISCOUNT,
            BusinessConcept.AGE,
            BusinessConcept.TENURE,
            BusinessConcept.STATUS,
            BusinessConcept.EDUCATION,
            BusinessConcept.PERFORMANCE_RATING,
            BusinessConcept.GENDER,
            BusinessConcept.WORK_MODE,
            BusinessConcept.MARITAL_STATUS,
            BusinessConcept.SUBSCRIPTION_PLAN,
            BusinessConcept.MRR,
            BusinessConcept.CHURN,
            BusinessConcept.CARRIER,
            BusinessConcept.WEIGHT,
            BusinessConcept.DIAGNOSIS,
            BusinessConcept.PRODUCT_ID,
            BusinessConcept.CUSTOMER_ID,
        ]

        for concept in concept_priority:
            best_col: Optional[str] = None
            best_conf: float = 0.0

            for col in cols_to_evaluate:
                if col.name in used_columns:
                    continue

                is_match, conf = cls.matches_concept(
                    concept=concept,
                    col_name=col.name,
                    col_type=col.detected_type,
                    col_role=col.role,
                )

                if is_match and conf > best_conf:
                    best_col = col.name
                    best_conf = conf

            if best_col and best_conf > 0.0:
                mappings[concept] = best_col
                confidence_scores[concept] = best_conf
                used_columns.add(best_col)

        # Unmapped columns
        all_col_names = [col.name for col in columns_info]
        unmapped = [c for c in all_col_names if c not in used_columns]

        # Domain Inference Rules
        has_hr_concepts = (
            BusinessConcept.DEPARTMENT in mappings
            or BusinessConcept.EMPLOYEE_ID in mappings
            or BusinessConcept.JOB_TITLE in mappings
            or BusinessConcept.HIRE_DATE in mappings
            or BusinessConcept.SALARY in mappings
        )
        has_saas_concepts = (
            BusinessConcept.USER_ID in mappings
            or BusinessConcept.SUBSCRIPTION_PLAN in mappings
            or BusinessConcept.MRR in mappings
            or BusinessConcept.CHURN in mappings
        )
        has_logistics_concepts = (
            BusinessConcept.SHIPMENT_ID in mappings
            or BusinessConcept.CARRIER in mappings
            or BusinessConcept.WEIGHT in mappings
        )
        has_healthcare_concepts = (
            BusinessConcept.PATIENT_ID in mappings
            or BusinessConcept.DIAGNOSIS in mappings
        )
        has_sales_kpis = (
            BusinessConcept.SALE_PRICE in mappings
            or BusinessConcept.QUANTITY in mappings
            or BusinessConcept.REVENUE in mappings
        )
        has_products = BusinessConcept.PRODUCT in mappings or BusinessConcept.CATEGORY in mappings

        if has_hr_concepts and not has_sales_kpis:
            domain = "human_resources"
            dataset_type = "hr_workforce"
        elif has_saas_concepts and not has_products:
            domain = "saas_subscription"
            dataset_type = "saas_analytics"
        elif has_logistics_concepts and not has_sales_kpis:
            domain = "logistics_supply_chain"
            dataset_type = "logistics_analytics"
        elif has_healthcare_concepts:
            domain = "healthcare"
            dataset_type = "patient_records"
        elif has_sales_kpis and has_products:
            domain = "sales"
            dataset_type = "ecommerce_sales" if BusinessConcept.ORDER_ID in mappings else "retail_sales"
        elif has_sales_kpis:
            domain = "financial_transactions"
            dataset_type = "financial_sales"
        elif has_products:
            domain = "inventory"
            dataset_type = "product_inventory"
        else:
            domain = "generic_analytics"
            dataset_type = "tabular_data"

        return SemanticModelSchema(
            dataset_id=dataset_id,
            domain=domain,
            dataset_type=dataset_type,
            mappings=mappings,
            dimensions=dimensions,
            measures=measures,
            time_dimensions=time_dimensions,
            identifiers=identifiers,
            confidence_scores=confidence_scores,
            unmapped_columns=unmapped,
            created_at=datetime.now(timezone.utc),
        )


semantic_model_builder = SemanticModelBuilder()
