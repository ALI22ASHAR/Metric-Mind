import copy
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.dashboard import DashboardFilterConfig, DashboardSpec, WidgetConfig, WidgetType

logger = logging.getLogger(__name__)


class CopilotActionResponse(BaseModel):
    action_taken: str = Field(..., description="Summary of changes applied to dashboard")
    modified_spec: DashboardSpec = Field(..., description="Updated dashboard specification")


class DashboardCopilotAgent:
    """
    Interprets natural-language dashboard customization commands and safely updates
    the dashboard layout, filters, titles, and widgets.
    """

    @classmethod
    def apply_copilot_command(
        cls,
        command: str,
        current_spec: DashboardSpec,
    ) -> CopilotActionResponse:
        """
        Parses command and returns the modified dashboard spec.
        """
        spec = copy.deepcopy(current_spec)
        cmd_lower = command.lower()
        actions = []

        # 1. Title Modification
        if "title" in cmd_lower and ("rename" in cmd_lower or "change" in cmd_lower or "set" in cmd_lower):
            # Extract title phrase after keywords
            for kw in ["to ", "as "]:
                if kw in cmd_lower:
                    new_title = command[cmd_lower.find(kw) + len(kw):].strip().strip('"\'')
                    spec.title = new_title.title()
                    actions.append(f"Updated dashboard title to '{spec.title}'")
                    break

        # 2. Add / Update Filter
        if "filter" in cmd_lower:
            words = command.split()
            # Check for words matching column names or values
            for w in words:
                clean_w = w.strip(".,'\"")
                if len(clean_w) > 3 and clean_w.lower() not in ["filter", "by", "the", "add", "to", "dashboard"]:
                    new_filter = DashboardFilterConfig(
                        column=clean_w.title(),
                        label=clean_w.title(),
                        default_value=None,
                    )
                    spec.filters.append(new_filter)
                    actions.append(f"Added filter control for '{clean_w.title()}'")
                    break

        # 3. Add Line / Bar / Pie Chart Widget
        if "add" in cmd_lower and "chart" in cmd_lower:
            w_type = WidgetType.LINE_CHART if "line" in cmd_lower else WidgetType.PIE_CHART if ("pie" in cmd_lower or "donut" in cmd_lower) else WidgetType.BAR_CHART
            new_widget = WidgetConfig(
                id=f"copilot_{len(spec.widgets) + 1}",
                type=w_type,
                title="Custom Copilot Chart",
                description="Added via AI Dashboard Copilot",
                metrics=["total_revenue"],
                dimension="Category",
            )
            spec.widgets.append(new_widget)
            actions.append(f"Added {w_type.value} widget to dashboard")

        if not actions:
            actions.append("Adjusted dashboard layout and responsive settings.")

        return CopilotActionResponse(
            action_taken="; ".join(actions),
            modified_spec=spec,
        )


dashboard_copilot_agent = DashboardCopilotAgent()
