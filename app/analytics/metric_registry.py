from typing import Dict, List, Optional
from app.schemas.metrics import MetricDefinition, MetricResult, MetricType
from app.schemas.semantic import BusinessConcept, SemanticModelSchema


class MetricCapabilityAnalyzer:
    """
    Evaluates semantic model mappings to identify all deterministically computable KPIs
    and generates compiled DuckDB SQL expressions.
    """

    @classmethod
    def get_computable_metrics(cls, semantic_model: SemanticModelSchema) -> List[MetricDefinition]:
        """
        Determines which standard business KPIs can be calculated from the available semantic concepts.
        """
        mappings = semantic_model.mappings
        computable: List[MetricDefinition] = []

        has_qty = BusinessConcept.QUANTITY in mappings
        has_sp = BusinessConcept.SALE_PRICE in mappings
        has_cp = BusinessConcept.COST_PRICE in mappings
        has_rev = BusinessConcept.REVENUE in mappings
        has_order = BusinessConcept.ORDER_ID in mappings
        has_discount = BusinessConcept.DISCOUNT in mappings

        qty_col = mappings.get(BusinessConcept.QUANTITY, "")
        sp_col = mappings.get(BusinessConcept.SALE_PRICE, "")
        cp_col = mappings.get(BusinessConcept.COST_PRICE, "")
        rev_col = mappings.get(BusinessConcept.REVENUE, "")
        order_col = mappings.get(BusinessConcept.ORDER_ID, "")
        disc_col = mappings.get(BusinessConcept.DISCOUNT, "")

        # 1. Total Revenue
        if has_qty and has_sp:
            computable.append(
                MetricDefinition(
                    id="total_revenue",
                    name="total_revenue",
                    label="Total Revenue",
                    description="Total gross sales revenue generated across all transactions",
                    metric_type=MetricType.CURRENCY,
                    unit="$",
                    is_computable=True,
                    required_concepts=[BusinessConcept.QUANTITY, BusinessConcept.SALE_PRICE],
                    sql_template=f"SUM({qty_col} * {sp_col})",
                    format_spec="${:,.2f}",
                )
            )
        elif has_rev:
            computable.append(
                MetricDefinition(
                    id="total_revenue",
                    name="total_revenue",
                    label="Total Revenue",
                    description="Total gross sales revenue generated across all transactions",
                    metric_type=MetricType.CURRENCY,
                    unit="$",
                    is_computable=True,
                    required_concepts=[BusinessConcept.REVENUE],
                    sql_template=f"SUM({rev_col})",
                    format_spec="${:,.2f}",
                )
            )

                                # Removed duplicate format_spec
        if has_qty and has_cp:
            computable.append(
                MetricDefinition(
                    id="total_cost",
                    name="total_cost",
                    label="Total Cost",
                    description="Total cost of goods sold (COGS) across all transactions",
                    metric_type=MetricType.CURRENCY,
                    unit="$",
                    is_computable=True,
                    required_concepts=[BusinessConcept.QUANTITY, BusinessConcept.COST_PRICE],
                    sql_template=f"SUM({qty_col} * {cp_col})",
                    format_spec="${:,.2f}",
                )
            )
        elif has_cp:
            computable.append(
                MetricDefinition(
                    id="total_cost",
                    name="total_cost",
                    label="Total Cost",
                    description="Total cost across all transactions",
                    metric_type=MetricType.CURRENCY,
                    unit="$",
                    is_computable=True,
                    required_concepts=[BusinessConcept.COST_PRICE],
                    sql_template=f"SUM({cp_col})",
                    format_spec="${:,.2f}",
                )
            )

        # 3. Total Profit
        if has_qty and has_sp and has_cp:
            computable.append(
                MetricDefinition(
                    id="total_profit",
                    name="total_profit",
                    label="Total Profit",
                    description="Net profit after subtracting cost from sales revenue",
                    metric_type=MetricType.CURRENCY,
                    unit="$",
                    is_computable=True,
                    required_concepts=[BusinessConcept.QUANTITY, BusinessConcept.SALE_PRICE, BusinessConcept.COST_PRICE],
                    sql_template=f"SUM(({sp_col} - {cp_col}) * {qty_col})",
                    format_spec="${:,.2f}",
                )
            )
        elif has_rev and has_cp:
            computable.append(
                MetricDefinition(
                    id="total_profit",
                    name="total_profit",
                    label="Total Profit",
                    description="Net profit calculated from revenue minus cost",
                    metric_type=MetricType.CURRENCY,
                    unit="$",
                    is_computable=True,
                    required_concepts=[BusinessConcept.REVENUE, BusinessConcept.COST_PRICE],
                    sql_template=f"SUM({rev_col} - {cp_col})",
                    format_spec="${:,.2f}",
                )
            )

        # 4. Profit Margin (%)
        if has_qty and has_sp and has_cp:
            computable.append(
                MetricDefinition(
                    id="profit_margin",
                    name="profit_margin",
                    label="Profit Margin",
                    description="Percentage of total revenue retained as net profit",
                    metric_type=MetricType.PERCENTAGE,
                    unit="%",
                    is_computable=True,
                    required_concepts=[BusinessConcept.QUANTITY, BusinessConcept.SALE_PRICE, BusinessConcept.COST_PRICE],
                    sql_template=f"(SUM(({sp_col} - {cp_col}) * {qty_col}) / NULLIF(SUM({sp_col} * {qty_col}), 0)) * 100.0",
                    format_spec="{:.2f}%",
                )
            )

        # 5. Total Units Sold
        if has_qty:
            computable.append(
                MetricDefinition(
                    id="units_sold",
                    name="units_sold",
                    label="Total Units Sold",
                    description="Aggregate quantity of items sold",
                    metric_type=MetricType.QUANTITY,
                    unit="units",
                    is_computable=True,
                    required_concepts=[BusinessConcept.QUANTITY],
                    sql_template=f"SUM({qty_col})",
                    format_spec="{:,.0f} units",
                )
            )

        # 6. Total Orders
        if has_order:
            computable.append(
                MetricDefinition(
                    id="total_orders",
                    name="total_orders",
                    label="Total Orders",
                    description="Distinct count of completed orders or transactions",
                    metric_type=MetricType.COUNT,
                    unit="orders",
                    is_computable=True,
                    required_concepts=[BusinessConcept.ORDER_ID],
                    sql_template=f"COUNT(DISTINCT {order_col})",
                    format_spec="{:,.0f}",
                )
            )
        else:
            computable.append(
                MetricDefinition(
                    id="total_orders",
                    name="total_orders",
                    label="Total Transactions",
                    description="Total record count of transactions",
                    metric_type=MetricType.COUNT,
                    unit="txs",
                    is_computable=True,
                    required_concepts=[],
                    sql_template="COUNT(*)",
                    format_spec="{:,.0f}",
                )
            )

        # 7. Average Order Value (AOV)
        if has_order and has_qty and has_sp:
            computable.append(
                MetricDefinition(
                    id="average_order_value",
                    name="average_order_value",
                    label="Average Order Value (AOV)",
                    description="Average revenue generated per individual order",
                    metric_type=MetricType.CURRENCY,
                    unit="$",
                    is_computable=True,
                    required_concepts=[BusinessConcept.ORDER_ID, BusinessConcept.QUANTITY, BusinessConcept.SALE_PRICE],
                    sql_template=f"SUM({qty_col} * {sp_col}) / NULLIF(COUNT(DISTINCT {order_col}), 0)",
                    format_spec="${:,.2f}",
                )
            )

        # 8. Average Unit Price
        if has_sp:
            computable.append(
                MetricDefinition(
                    id="average_unit_price",
                    name="average_unit_price",
                    label="Average Unit Price",
                    description="Mean selling price across all items",
                    metric_type=MetricType.CURRENCY,
                    unit="$",
                    is_computable=True,
                    required_concepts=[BusinessConcept.SALE_PRICE],
                    sql_template=f"AVG({sp_col})",
                    format_spec="${:,.2f}",
                )
            )

        # 9. Total Discount
        if has_discount:
            computable.append(
                MetricDefinition(
                    id="total_discount",
                    name="total_discount",
                    label="Total Discount",
                    description="Cumulative monetary discount awarded",
                    metric_type=MetricType.CURRENCY,
                    unit="$",
                    is_computable=True,
                    required_concepts=[BusinessConcept.DISCOUNT],
                    sql_template=f'SUM("{disc_col}")',
                    format_spec="${:,.2f}",
                )
            )

        # 10. Max Order / Peak Transaction Value
        if (has_qty and has_sp) or has_rev:
            rev_expr = f"{qty_col} * {sp_col}" if (has_qty and has_sp) else rev_col
            computable.append(
                MetricDefinition(
                    id="max_order_value",
                    name="max_order_value",
                    label="Peak Transaction Value",
                    description="Highest single transaction amount recorded",
                    metric_type=MetricType.CURRENCY,
                    unit="$",
                    is_computable=True,
                    required_concepts=[],
                    sql_template=f"MAX({rev_expr})",
                    format_spec="${:,.2f}",
                )
            )

        # 11. Average Profit Per Order
        if has_order and ((has_qty and has_sp and has_cp) or (has_rev and has_cp)):
            profit_expr = f"({sp_col} - {cp_col}) * {qty_col}" if (has_qty and has_sp and has_cp) else f"{rev_col} - {cp_col}"
            computable.append(
                MetricDefinition(
                    id="avg_profit_per_order",
                    name="avg_profit_per_order",
                    label="Avg Profit / Order",
                    description="Mean net profit generated per single order",
                    metric_type=MetricType.CURRENCY,
                    unit="$",
                    is_computable=True,
                    required_concepts=[BusinessConcept.ORDER_ID],
                    sql_template=f"SUM({profit_expr}) / NULLIF(COUNT(DISTINCT {order_col}), 0)",
                    format_spec="${:,.2f}",
                )
            )

        # 12. Units Per Order (Basket Size)
        if has_order and has_qty:
            computable.append(
                MetricDefinition(
                    id="units_per_order",
                    name="units_per_order",
                    label="Basket Size (Units/Order)",
                    description="Average items purchased per individual transaction",
                    metric_type=MetricType.RATIO,
                    unit="items",
                    is_computable=True,
                    required_concepts=[BusinessConcept.ORDER_ID, BusinessConcept.QUANTITY],
                    sql_template=f"SUM({qty_col}) / NULLIF(COUNT(DISTINCT {order_col}), 0)",
                    format_spec="{:.1f} items",
                )
            )

        # 13. Discount Rate %
        if has_discount and (has_rev or (has_qty and has_sp)):
            rev_expr = f"SUM({qty_col} * {sp_col})" if (has_qty and has_sp) else f"SUM({rev_col})"
            computable.append(
                MetricDefinition(
                    id="discount_rate",
                    name="discount_rate",
                    label="Discount Rate",
                    description="Percentage of gross potential revenue discounted",
                    metric_type=MetricType.PERCENTAGE,
                    unit="%",
                    is_computable=True,
                    required_concepts=[BusinessConcept.DISCOUNT],
                    sql_template=f'(SUM("{disc_col}") / NULLIF(({rev_expr}) + SUM("{disc_col}"), 0)) * 100.0',
                    format_spec="{:.2f}%",
                )
            )

        # 14. Active Products Count
        prod_col = semantic_model.product_column or mappings.get(BusinessConcept.PRODUCT, "")
        if prod_col:
            computable.append(
                MetricDefinition(
                    id="active_products",
                    name="active_products",
                    label="Active Products",
                    description="Distinct count of active product SKUs",
                    metric_type=MetricType.COUNT,
                    unit="SKUs",
                    is_computable=True,
                    required_concepts=[],
                    sql_template=f'COUNT(DISTINCT "{prod_col}")',
                    format_spec="{:,}",
                )
            )


        # =========================================================================
        # HR & WORKFORCE DOMAIN METRICS
        # =========================================================================
        emp_col = mappings.get(BusinessConcept.EMPLOYEE_ID, "")
        dept_col = mappings.get(BusinessConcept.DEPARTMENT, "")
        salary_col = mappings.get(BusinessConcept.SALARY, "")
        age_col = mappings.get(BusinessConcept.AGE, "")
        tenure_col = mappings.get(BusinessConcept.TENURE, "")
        city_col = mappings.get(BusinessConcept.CITY, "")
        state_col = mappings.get(BusinessConcept.STATE, "")
        hire_date_col = mappings.get(BusinessConcept.HIRE_DATE, "")
        status_col = mappings.get(BusinessConcept.STATUS, "")
        performance_col = mappings.get(BusinessConcept.PERFORMANCE_RATING, "")

        if semantic_model.domain == "human_resources" or (dept_col or emp_col):
            computable.append(
                MetricDefinition(
                    id="total_employees",
                    name="total_employees",
                    label="Total Headcount",
                    description="Total active employee headcount across all departments",
                    metric_type=MetricType.COUNT,
                    unit="Employees",
                    is_computable=True,
                    required_concepts=[],
                    sql_template="COUNT(*)",
                    format_spec="{:,.0f}",
                )
            )
            if hire_date_col:
                # Aggregate *flow* metric — count of records per period, used by the
                # "Workforce Growth / Hiring Trajectory" line chart.
                computable.append(
                    MetricDefinition(
                        id="hires_over_time",
                        name="hires_over_time",
                        label="Hires (per period)",
                        description="Number of employees hired during each time period",
                        metric_type=MetricType.COUNT,
                        unit="Hires",
                        is_computable=True,
                        required_concepts=[BusinessConcept.HIRE_DATE],
                        sql_template="COUNT(*)",
                        format_spec="{:,.0f}",
                    )
                )
                # Annualized hire rate: hires / total headcount, as a percentage
                computable.append(
                    MetricDefinition(
                        id="hire_rate",
                        name="hire_rate",
                        label="Hire Rate",
                        description="Ratio of total hires to current headcount, as a percentage",
                        metric_type=MetricType.PERCENTAGE,
                        unit="%",
                        is_computable=True,
                        required_concepts=[BusinessConcept.HIRE_DATE],
                        sql_template="(COUNT(*) / NULLIF(COUNT(*), 0)) * 100.0",
                        format_spec="{:.2f}%",
                    )
                )
            if status_col:
                # Active employees: rows where the status column indicates active employment.
                computable.append(
                    MetricDefinition(
                        id="active_employees",
                        name="active_employees",
                        label="Active Employees",
                        description="Count of employees currently marked as active",
                        metric_type=MetricType.COUNT,
                        unit="Active",
                        is_computable=True,
                        required_concepts=[BusinessConcept.STATUS],
                        sql_template=(
                            f'SUM(CASE WHEN LOWER(CAST("{status_col}" AS VARCHAR)) IN '
                            f'(\'active\', \'employed\', \'current\', \'true\', \'1\', \'yes\') THEN 1 ELSE 0 END)'
                        ),
                        format_spec="{:,.0f}",
                    )
                )
                # Turnover rate: percentage of inactive/terminated employees.
                computable.append(
                    MetricDefinition(
                        id="turnover_rate",
                        name="turnover_rate",
                        label="Turnover Rate",
                        description="Percentage of workforce marked as separated/exited",
                        metric_type=MetricType.PERCENTAGE,
                        unit="%",
                        is_computable=True,
                        required_concepts=[BusinessConcept.STATUS],
                        sql_template=(
                            f'AVG(CASE WHEN LOWER(CAST("{status_col}" AS VARCHAR)) IN '
                            f'(\'inactive\', \'terminated\', \'exited\', \'left\', \'separated\', \'false\', \'0\', \'no\') '
                            f'THEN 1.0 ELSE 0.0 END) * 100.0'
                        ),
                        format_spec="{:.2f}%",
                    )
                )
            if performance_col:
                computable.append(
                    MetricDefinition(
                        id="avg_performance_rating",
                        name="avg_performance_rating",
                        label="Average Performance",
                        description="Mean employee performance rating",
                        metric_type=MetricType.RATIO,
                        unit="",
                        is_computable=True,
                        required_concepts=[BusinessConcept.PERFORMANCE_RATING],
                        sql_template=f'AVG("{performance_col}")',
                        format_spec="{:.2f}",
                    )
                )
            if dept_col:
                computable.append(
                    MetricDefinition(
                        id="active_departments",
                        name="active_departments",
                        label="Active Departments",
                        description="Count of unique operational departments",
                        metric_type=MetricType.COUNT,
                        unit="Depts",
                        is_computable=True,
                        required_concepts=[BusinessConcept.DEPARTMENT],
                        sql_template=f'COUNT(DISTINCT "{dept_col}")',
                        format_spec="{:,.0f}",
                    )
                )
            if city_col or state_col:
                loc_col = city_col or state_col
                computable.append(
                    MetricDefinition(
                        id="workforce_locations",
                        name="workforce_locations",
                        label="Workforce Locations",
                        description="Distinct geographic locations and operational offices",
                        metric_type=MetricType.COUNT,
                        unit="Cities",
                        is_computable=True,
                        required_concepts=[],
                        sql_template=f'COUNT(DISTINCT "{loc_col}")',
                        format_spec="{:,.0f}",
                    )
                )
            if salary_col:
                computable.append(
                    MetricDefinition(
                        id="average_salary",
                        name="average_salary",
                        label="Average Salary",
                        description="Mean annual compensation across employees",
                        metric_type=MetricType.CURRENCY,
                        unit="$",
                        is_computable=True,
                        required_concepts=[BusinessConcept.SALARY],
                        sql_template=f'AVG("{salary_col}")',
                        format_spec="${:,.2f}",
                    )
                )
            if age_col:
                computable.append(
                    MetricDefinition(
                        id="average_age",
                        name="average_age",
                        label="Average Employee Age",
                        description="Mean age across employee workforce",
                        metric_type=MetricType.RATIO,
                        unit="yrs",
                        is_computable=True,
                        required_concepts=[BusinessConcept.AGE],
                        sql_template=f'AVG("{age_col}")',
                        format_spec="{:.1f} yrs",
                    )
                )
            if tenure_col:
                computable.append(
                    MetricDefinition(
                        id="average_tenure",
                        name="average_tenure",
                        label="Average Tenure",
                        description="Mean years of service at company",
                        metric_type=MetricType.RATIO,
                        unit="yrs",
                        is_computable=True,
                        required_concepts=[BusinessConcept.TENURE],
                        sql_template=f'AVG("{tenure_col}")',
                        format_spec="{:.1f} yrs",
                    )
                )

        # =========================================================================
        # SAAS, LOGISTICS & GENERIC METRICS FALLBACK
        # =========================================================================
        user_col = mappings.get(BusinessConcept.USER_ID, "")
        plan_col = mappings.get(BusinessConcept.SUBSCRIPTION_PLAN, "")
        mrr_col = mappings.get(BusinessConcept.MRR, "")
        if semantic_model.domain == "saas_subscription" or (user_col and plan_col):
            computable.append(
                MetricDefinition(
                    id="total_users",
                    name="total_users",
                    label="Total Subscribers",
                    description="Total user accounts on platform",
                    metric_type=MetricType.COUNT,
                    unit="Users",
                    is_computable=True,
                    required_concepts=[],
                    sql_template="COUNT(*)",
                    format_spec="{:,}",
                )
            )
            if mrr_col:
                computable.append(
                    MetricDefinition(
                        id="total_mrr",
                        name="total_mrr",
                        label="Total MRR",
                        description="Monthly Recurring Revenue",
                        metric_type=MetricType.CURRENCY,
                        unit="$",
                        is_computable=True,
                        required_concepts=[BusinessConcept.MRR],
                        sql_template=f'SUM("{mrr_col}")',
                        format_spec="${:,.2f}",
                    )
                )
            if plan_col:
                computable.append(
                    MetricDefinition(
                        id="active_plans",
                        name="active_plans",
                        label="Active Plans",
                        description="Distinct subscription plans represented in the dataset",
                        metric_type=MetricType.COUNT,
                        unit="Plans",
                        is_computable=True,
                        required_concepts=[BusinessConcept.SUBSCRIPTION_PLAN],
                        sql_template=f'COUNT(DISTINCT "{plan_col}")',
                        format_spec="{:,}",
                    )
                )
            churn_col = mappings.get(BusinessConcept.CHURN, "")
            if churn_col:
                computable.append(
                    MetricDefinition(
                        id="churn_rate",
                        name="churn_rate",
                        label="Churn Rate",
                        description="Percentage of records marked as churned",
                        metric_type=MetricType.PERCENTAGE,
                        unit="%",
                        is_computable=True,
                        required_concepts=[BusinessConcept.CHURN],
                        sql_template=f'AVG(CASE WHEN CAST("{churn_col}" AS VARCHAR) IN (\'true\', \'1\', \'yes\', \'churned\') THEN 1.0 ELSE 0.0 END) * 100.0',
                        format_spec="{:.2f}%",
                    )
                )

        # =========================================================================
        # LOGISTICS & HEALTHCARE DOMAIN METRICS
        # =========================================================================
        shipment_col = mappings.get(BusinessConcept.SHIPMENT_ID, "")
        carrier_col = mappings.get(BusinessConcept.CARRIER, "")
        weight_col = mappings.get(BusinessConcept.WEIGHT, "")
        if semantic_model.domain == "logistics_supply_chain" or shipment_col or carrier_col:
            computable.append(
                MetricDefinition(
                    id="total_shipments",
                    name="total_shipments",
                    label="Total Shipments",
                    description="Distinct shipments processed",
                    metric_type=MetricType.COUNT,
                    unit="Shipments",
                    is_computable=True,
                    required_concepts=[],
                    sql_template=f'COUNT(DISTINCT "{shipment_col}")' if shipment_col else "COUNT(*)",
                    format_spec="{:,}",
                )
            )
            if carrier_col:
                computable.append(
                    MetricDefinition(
                        id="active_carriers",
                        name="active_carriers",
                        label="Active Carriers",
                        description="Distinct carriers handling shipments",
                        metric_type=MetricType.COUNT,
                        unit="Carriers",
                        is_computable=True,
                        required_concepts=[BusinessConcept.CARRIER],
                        sql_template=f'COUNT(DISTINCT "{carrier_col}")',
                        format_spec="{:,}",
                    )
                )
            if weight_col:
                computable.append(
                    MetricDefinition(
                        id="average_weight",
                        name="average_weight",
                        label="Average Shipment Weight",
                        description="Mean shipment weight",
                        metric_type=MetricType.RATIO,
                        unit="units",
                        is_computable=True,
                        required_concepts=[BusinessConcept.WEIGHT],
                        sql_template=f'AVG("{weight_col}")',
                        format_spec="{:,.2f}",
                    )
                )

        patient_col = mappings.get(BusinessConcept.PATIENT_ID, "")
        diagnosis_col = mappings.get(BusinessConcept.DIAGNOSIS, "")
        if semantic_model.domain == "healthcare" or patient_col or diagnosis_col:
            computable.append(
                MetricDefinition(
                    id="total_patients",
                    name="total_patients",
                    label="Total Patients",
                    description="Distinct patients represented in the dataset",
                    metric_type=MetricType.COUNT,
                    unit="Patients",
                    is_computable=True,
                    required_concepts=[],
                    sql_template=f'COUNT(DISTINCT "{patient_col}")' if patient_col else "COUNT(*)",
                    format_spec="{:,}",
                )
            )
            if diagnosis_col:
                computable.append(
                    MetricDefinition(
                        id="active_diagnoses",
                        name="active_diagnoses",
                        label="Diagnoses Recorded",
                        description="Distinct diagnoses represented in the dataset",
                        metric_type=MetricType.COUNT,
                        unit="Diagnoses",
                        is_computable=True,
                        required_concepts=[BusinessConcept.DIAGNOSIS],
                        sql_template=f'COUNT(DISTINCT "{diagnosis_col}")',
                        format_spec="{:,}",
                    )
                )

        # Generic Fallback Guarantee: Always provide at least 3-4 computable KPIs for ANY dataset
        if len(computable) < 3:
            computable.append(
                MetricDefinition(
                    id="total_records",
                    name="total_records",
                    label="Total Volume / Records",
                    description="Total record count in dataset",
                    metric_type=MetricType.COUNT,
                    unit="Records",
                    is_computable=True,
                    required_concepts=[],
                    sql_template="COUNT(*)",
                    format_spec="{:,}",
                )
            )
            # Add distinct count on first 2 categorical dimensions if available
            dims = semantic_model.dimensions or []
            for i, dim_name in enumerate(dims[:2]):
                dim_metric_id = f"distinct_{dim_name.lower().replace(' ', '_')}"
                if not any(m.id == dim_metric_id for m in computable):
                    computable.append(
                        MetricDefinition(
                            id=dim_metric_id,
                            name=dim_metric_id,
                            label=f"Unique {dim_name} Count",
                            description=f"Count of distinct {dim_name} categories",
                            metric_type=MetricType.COUNT,
                            unit="Groups",
                            is_computable=True,
                            required_concepts=[],
                            sql_template=f'COUNT(DISTINCT "{dim_name}")',
                            format_spec="{:,}",
                        )
                    )

            # Add average on numeric measures if available
            measures = semantic_model.measures or []
            for num_col in measures[:2]:
                avg_id = f"avg_{num_col.lower().replace(' ', '_')}"
                if not any(m.id == avg_id for m in computable):
                    computable.append(
                        MetricDefinition(
                            id=avg_id,
                            name=avg_id,
                            label=f"Average {num_col.replace('_', ' ').title()}",
                            description=f"Mean calculated value of {num_col}",
                            metric_type=MetricType.RATIO,
                            unit="",
                            is_computable=True,
                            required_concepts=[],
                            sql_template=f'AVG("{num_col}")',
                            format_spec="{:,.2f}",
                        )
                    )

        # Include dataset-registered custom metrics if available
        if hasattr(semantic_model, "dataset_id") and semantic_model.dataset_id in cls._custom_metrics:
            computable.extend(cls._custom_metrics[semantic_model.dataset_id])

        return computable

    _custom_metrics: Dict[str, List[MetricDefinition]] = {}

    @classmethod
    def register_custom_metric(cls, dataset_id: str, metric_def: MetricDefinition) -> None:
        """
        Stores a user-defined custom metric for the dataset.
        """
        if dataset_id not in cls._custom_metrics:
            cls._custom_metrics[dataset_id] = []
        # Replace if existing with same id
        cls._custom_metrics[dataset_id] = [
            m for m in cls._custom_metrics[dataset_id] if m.id != metric_def.id
        ]
        cls._custom_metrics[dataset_id].append(metric_def)

    @classmethod
    def get_custom_metrics_for_dataset(cls, dataset_id: str) -> List[MetricDefinition]:
        """
        Returns all custom metrics defined for a dataset.
        """
        return cls._custom_metrics.get(dataset_id, [])

    @classmethod
    def format_metric_value(cls, value: Optional[float], metric_def: MetricDefinition) -> str:
        """
        Formats a numeric float metric value into human-readable representation.
        """
        if value is None:
            return "N/A"
        try:
            return metric_def.format_spec.format(value)
        except Exception:
            return str(round(value, 2))


metric_capability_analyzer = MetricCapabilityAnalyzer()

