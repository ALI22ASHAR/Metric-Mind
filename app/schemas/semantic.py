from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class BusinessConcept(str):
    DATE = "date_column"
    QUANTITY = "quantity_column"
    SALE_PRICE = "sale_price_column"
    COST_PRICE = "cost_price_column"
    REVENUE = "revenue_column"
    PROFIT = "profit_column"
    PRODUCT = "product_column"
    PRODUCT_ID = "product_id_column"
    CATEGORY = "category_column"
    CUSTOMER = "customer_column"
    CUSTOMER_ID = "customer_id_column"
    ORDER_ID = "order_id_column"
    CITY = "city_column"
    STATE = "state_column"
    COUNTRY = "country_column"
    REGION = "region_column"
    DISCOUNT = "discount_column"
    # HR & Workforce Concepts
    EMPLOYEE_ID = "employee_id_column"
    EMPLOYEE_NAME = "employee_name_column"
    DEPARTMENT = "department_column"
    JOB_TITLE = "job_title_column"
    HIRE_DATE = "hire_date_column"
    SALARY = "salary_column"
    AGE = "age_column"
    TENURE = "tenure_column"
    STATUS = "status_column"
    EDUCATION = "education_column"
    PERFORMANCE_RATING = "performance_rating_column"
    GENDER = "gender_column"
    WORK_MODE = "work_mode_column"
    MARITAL_STATUS = "marital_status_column"
    SALARY_BAND = "salary_band_column"
    # SaaS & Subscription Concepts
    USER_ID = "user_id_column"
    SUBSCRIPTION_PLAN = "subscription_plan_column"
    MRR = "mrr_column"
    CHURN = "churn_column"
    # Logistics & Operations Concepts
    SHIPMENT_ID = "shipment_id_column"
    CARRIER = "carrier_column"
    WEIGHT = "weight_column"
    # Healthcare Concepts
    PATIENT_ID = "patient_id_column"
    DIAGNOSIS = "diagnosis_column"


class SemanticMappingUpdate(BaseModel):
    domain: Optional[str] = Field(None, description="Business domain (e.g. hr, sales, ecommerce, retail, healthcare, logistics)")
    dataset_type: Optional[str] = Field(None, description="Dataset type classification")
    mappings: Dict[str, Optional[str]] = Field(..., description="Map of business concepts to column names")


class SemanticModelSchema(BaseModel):
    dataset_id: str = Field(..., description="Associated dataset ID")
    domain: str = Field("generic_analytics", description="Business domain (e.g. hr, sales, ecommerce, healthcare, logistics, generic_analytics)")
    dataset_type: str = Field("generic_business", description="Specific dataset classification")
    mappings: Dict[str, str] = Field(default_factory=dict, description="Mapped standard business concepts to column names")
    dimensions: List[str] = Field(default_factory=list, description="Categorical dimension columns")
    measures: List[str] = Field(default_factory=list, description="Numeric quantitative measure columns")
    time_dimensions: List[str] = Field(default_factory=list, description="Date and timestamp columns")
    identifiers: List[str] = Field(default_factory=list, description="Key and ID columns")
    confidence_scores: Dict[str, float] = Field(default_factory=dict, description="Confidence score per mapping (0.0 - 1.0)")
    unmapped_columns: List[str] = Field(default_factory=list, description="Columns not mapped to standard concepts")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")

    # Helper getters for common concepts
    @property
    def date_column(self) -> Optional[str]:
        # HR trends must use hiring dates, not unrelated dates such as birth dates.
        if self.domain == "human_resources":
            return (
                self.mappings.get(BusinessConcept.HIRE_DATE)
                or self.mappings.get(BusinessConcept.DATE)
                or (self.time_dimensions[0] if self.time_dimensions else None)
            )
        return (
            self.mappings.get(BusinessConcept.DATE)
            or self.mappings.get(BusinessConcept.HIRE_DATE)
            or (self.time_dimensions[0] if self.time_dimensions else None)
        )

    @property
    def hire_date_column(self) -> Optional[str]:
        return self.mappings.get(BusinessConcept.HIRE_DATE)

    @property
    def employee_name_column(self) -> Optional[str]:
        return self.mappings.get(BusinessConcept.EMPLOYEE_NAME)

    @property
    def quantity_column(self) -> Optional[str]:
        return self.mappings.get(BusinessConcept.QUANTITY)

    @property
    def sale_price_column(self) -> Optional[str]:
        return self.mappings.get(BusinessConcept.SALE_PRICE)

    @property
    def cost_price_column(self) -> Optional[str]:
        return self.mappings.get(BusinessConcept.COST_PRICE)

    @property
    def product_column(self) -> Optional[str]:
        return self.mappings.get(BusinessConcept.PRODUCT)

    @property
    def category_column(self) -> Optional[str]:
        return self.mappings.get(BusinessConcept.CATEGORY)

    @property
    def region_column(self) -> Optional[str]:
        return self.mappings.get(BusinessConcept.REGION)

    @property
    def country_column(self) -> Optional[str]:
        return self.mappings.get(BusinessConcept.COUNTRY)

    @property
    def customer_column(self) -> Optional[str]:
        return self.mappings.get(BusinessConcept.CUSTOMER)

    @property
    def discount_column(self) -> Optional[str]:
        return self.mappings.get(BusinessConcept.DISCOUNT)

    def validate_against_columns(self, valid_columns: List[str]) -> None:
        """
        Validates that all mapped column names exist in the provided column list.
        Raises ValueError if any nonexistent column is referenced.
        """
        valid_set = set(valid_columns)
        for concept, col_name in self.mappings.items():
            if col_name and col_name not in valid_set:
                raise ValueError(
                    f"Semantic mapping for concept '{concept}' references nonexistent column '{col_name}'. "
                    f"Available columns: {sorted(list(valid_set))}"
                )

    model_config = ConfigDict(from_attributes=True)
