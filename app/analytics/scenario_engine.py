from typing import List, Optional
from fastapi import HTTPException, status
from app.analytics.duckdb_engine import duckdb_engine
from app.schemas.analytics import DimensionFilter, FilterOperator
from app.schemas.scenario import (
    ScenarioImpact,
    ScenarioSimulationRequest,
    ScenarioSimulationResponse,
)
from app.schemas.semantic import BusinessConcept, SemanticModelSchema


class ScenarioSimulationEngine:
    """
    Parametric what-if financial simulation engine evaluating pricing, volume,
    and cost shifts deterministically using DuckDB.
    """

    @classmethod
    def simulate_scenario(
        cls,
        dataset_id: str,
        parquet_path: str,
        semantic_model: SemanticModelSchema,
        request: ScenarioSimulationRequest,
    ) -> ScenarioSimulationResponse:
        """
        Calculates simulated impact of pricing, volume, and cost changes.
        """
        mappings = semantic_model.mappings
        qty_col = mappings.get(BusinessConcept.QUANTITY, "Quantity")
        sp_col = mappings.get(BusinessConcept.SALE_PRICE, "Sale_Price")
        cp_col = mappings.get(BusinessConcept.COST_PRICE, "Cost_Price")

        p_mult = 1.0 + (request.price_change_pct / 100.0)
        c_mult = 1.0 + (request.cost_change_pct / 100.0)
        v_mult = 1.0 + (request.volume_change_pct / 100.0)

        where_clause = ""
        filter_params = []
        if request.target_dimension_filter:
            valid_columns = set(semantic_model.dimensions or [])
            valid_columns.update(semantic_model.identifiers or [])
            conditions = []
            for col, val in request.target_dimension_filter.items():
                if col not in valid_columns:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Scenario filter column '{col}' is not a valid dataset dimension.",
                    )
                clause, params = duckdb_engine.build_where_clause([
                    DimensionFilter(column=col, operator=FilterOperator.EQ, value=val)
                ])
                conditions.append(clause.removeprefix("WHERE "))
                filter_params.extend(params)
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

        sql = f"""
            SELECT 
                SUM({qty_col} * {sp_col}) AS base_revenue,
                SUM({qty_col} * {cp_col}) AS base_cost,
                SUM(({qty_col} * {v_mult}) * ({sp_col} * {p_mult})) AS sim_revenue,
                SUM(({qty_col} * {v_mult}) * ({cp_col} * {c_mult})) AS sim_cost,
                SUM({qty_col}) AS base_qty,
                SUM({qty_col} * {v_mult}) AS sim_qty
            FROM '{parquet_path}'
            {where_clause}
        """

        res = duckdb_engine.execute_safe_query(parquet_path=parquet_path, sql=sql, params=filter_params)
        row = res.rows[0] if res.rows else {}

        base_rev = float(row.get("base_revenue") or 0.0)
        base_cost = float(row.get("base_cost") or 0.0)
        base_profit = base_rev - base_cost
        base_margin = (base_profit / base_rev * 100.0) if base_rev > 0 else 0.0

        sim_rev = float(row.get("sim_revenue") or 0.0)
        sim_cost = float(row.get("sim_cost") or 0.0)
        sim_profit = sim_rev - sim_cost
        sim_margin = (sim_profit / sim_rev * 100.0) if sim_rev > 0 else 0.0

        impacts: List[ScenarioImpact] = [
            ScenarioImpact(
                metric_id="total_revenue",
                baseline_value=round(base_rev, 2),
                simulated_value=round(sim_rev, 2),
                delta_value=round(sim_rev - base_rev, 2),
                delta_percentage=round(((sim_rev - base_rev) / base_rev * 100.0) if base_rev > 0 else 0.0, 1),
                formatted_baseline=f"${base_rev:,.2f}",
                formatted_simulated=f"${sim_rev:,.2f}",
            ),
            ScenarioImpact(
                metric_id="total_profit",
                baseline_value=round(base_profit, 2),
                simulated_value=round(sim_profit, 2),
                delta_value=round(sim_profit - base_profit, 2),
                delta_percentage=round(((sim_profit - base_profit) / base_profit * 100.0) if base_profit > 0 else 0.0, 1),
                formatted_baseline=f"${base_profit:,.2f}",
                formatted_simulated=f"${sim_profit:,.2f}",
            ),
            ScenarioImpact(
                metric_id="profit_margin",
                baseline_value=round(base_margin, 2),
                simulated_value=round(sim_margin, 2),
                delta_value=round(sim_margin - base_margin, 2),
                delta_percentage=round(((sim_margin - base_margin) / base_margin * 100.0) if base_margin > 0 else 0.0, 1),
                formatted_baseline=f"{base_margin:.1f}%",
                formatted_simulated=f"{sim_margin:.1f}%",
            ),
        ]

        profit_delta = sim_profit - base_profit
        sign = "increase" if profit_delta >= 0 else "decrease"
        takeaway = (
            f"Simulated parameters yield a net profit {sign} of ${abs(profit_delta):,.2f} "
            f"({impacts[1].delta_percentage:+.1f}%), shifting margin from {base_margin:.1f}% to {sim_margin:.1f}%."
        )

        return ScenarioSimulationResponse(
            dataset_id=dataset_id,
            price_change_pct=request.price_change_pct,
            cost_change_pct=request.cost_change_pct,
            volume_change_pct=request.volume_change_pct,
            filter_applied=request.target_dimension_filter,
            impacts=impacts,
            executive_takeaway=takeaway,
        )


scenario_simulation_engine = ScenarioSimulationEngine()
