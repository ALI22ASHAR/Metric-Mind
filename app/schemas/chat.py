from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    role: ChatRole
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class AnalyticalQueryPlan(BaseModel):
    """
    Structured analytical intent and compiled DuckDB SQL query.
    """
    thought_process: str = Field(..., description="Brief step-by-step reasoning behind the SQL logic")
    intent: str = Field("aggregate", description="Query analytical intent: 'aggregate', 'rank', 'filter', 'trend', 'compare'")
    target_metric: Optional[str] = Field(None, description="Primary business metric analyzed")
    target_dimension: Optional[str] = Field(None, description="Primary dimension grouped or filtered")
    sql_query: str = Field(..., description="Executable DuckDB SQL query over 'data' table")
    recommended_chart_type: str = Field(
        "table",
        description="Optimal visual representation: 'kpi_card', 'bar_chart', 'line_chart', 'pie_chart', 'table', 'none'",
    )


class ChatQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Natural-language business question")
    conversation_history: List[ChatMessage] = Field(
        default_factory=list,
        description="Prior conversational messages for context",
    )


class ChatQueryResponse(BaseModel):
    query_id: str = Field(..., description="Unique query execution identifier")
    question: str = Field(..., description="Original user question")
    answer_text: str = Field(..., description="Synthesized executive explanation of the analytical results")
    insights: List[str] = Field(default_factory=list, description="2-3 key takeaway bullet points")
    sql_query: str = Field(..., description="Validated DuckDB SQL query executed against the dataset")
    data: List[Dict[str, Any]] = Field(default_factory=list, description="Raw rows returned by the analytical query")
    chart_type: Optional[str] = Field(None, description="Auto-selected chart visualizer type")
    suggested_followups: List[str] = Field(default_factory=list, description="3 recommended follow-up analytical questions")
    execution_time_ms: float = Field(0.0, description="Total backend query and synthesis latency in milliseconds")

    model_config = ConfigDict(from_attributes=True)


class SuggestedQuestionsResponse(BaseModel):
    dataset_id: str
    questions: List[str]
