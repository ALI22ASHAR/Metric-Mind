from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ScenarioImpact(BaseModel):
    metric_id: str
    baseline_value: float
    simulated_value: float
    delta_value: float
    delta_percentage: float
    formatted_baseline: str
    formatted_simulated: str

    model_config = ConfigDict(from_attributes=True)


class ScenarioSimulationRequest(BaseModel):
    price_change_pct: float = Field(0.0, ge=-90.0, le=200.0, description="Price multiplier percentage (-50% to +100%)")
    cost_change_pct: float = Field(0.0, ge=-90.0, le=200.0, description="Cost multiplier percentage")
    volume_change_pct: float = Field(0.0, ge=-90.0, le=300.0, description="Volume/quantity multiplier percentage")
    target_dimension_filter: Optional[Dict[str, str]] = Field(None, description="Optional segment filter (e.g. {'Category': 'Electronics'})")

    model_config = ConfigDict(from_attributes=True)


class ScenarioSimulationResponse(BaseModel):
    dataset_id: str
    price_change_pct: float
    cost_change_pct: float
    volume_change_pct: float
    filter_applied: Optional[Dict[str, str]]
    impacts: List[ScenarioImpact]
    executive_takeaway: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
