from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class DatasetCase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    case_id: str = Field(alias="Case_ID")
    category: str = Field(alias="Category")
    query: str = Field(alias="Query")
    context: str | None = Field(default=None, alias="Context")
    expected_output: str = Field(alias="Expected_Output")

    @field_validator("case_id", "category", "query", "expected_output")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("字段不能为空")
        return str(value).strip()


class Dataset(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ds"))
    tenant_id: str
    name: str
    version: str = "v1"
    cases: list[DatasetCase]
    created_at: str = Field(default_factory=now_iso)


class HeaderPair(BaseModel):
    key: str
    value: str


class AgentEndpoint(BaseModel):
    id: str = Field(default_factory=lambda: new_id("agent"))
    tenant_id: str
    name: str
    url: HttpUrl
    headers: list[HeaderPair] = Field(default_factory=list)
    timeout_seconds: float = Field(default=60, ge=1, le=600)
    retries: int = Field(default=1, ge=0, le=5)
    created_at: str = Field(default_factory=now_iso)

    def header_dict(self) -> dict[str, str]:
        return {item.key: item.value for item in self.headers if item.key}


class JudgeProvider(str, Enum):
    openai_compatible = "openai_compatible"
    heuristic = "heuristic"


class JudgeConfig(BaseModel):
    id: str = Field(default_factory=lambda: new_id("judge"))
    tenant_id: str
    name: str
    provider: JudgeProvider = JudgeProvider.heuristic
    model_name: str = "heuristic-v1"
    base_url: HttpUrl | None = None
    api_key: str | None = None
    temperature: float = Field(default=0, ge=0, le=2)
    created_at: str = Field(default_factory=now_iso)


class EvaluationStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class EvaluationRequest(BaseModel):
    tenant_id: str
    dataset_id: str
    endpoint_id: str
    judge_id: str | None = None
    concurrency: int = Field(default=5, ge=1, le=100)


class EvaluationRun(BaseModel):
    id: str = Field(default_factory=lambda: new_id("eval"))
    tenant_id: str
    dataset_id: str
    endpoint_id: str
    judge_id: str | None = None
    concurrency: int = 5
    status: EvaluationStatus = EvaluationStatus.queued
    config_path: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    created_at: str = Field(default_factory=now_iso)


class AgentResult(BaseModel):
    output: str
    latency_ms: float
    status_code: int | None = None
    error: str | None = None


class JudgeScore(BaseModel):
    score: float = Field(ge=0, le=10)
    reasoning: str
    dimensions: dict[str, float] = Field(default_factory=dict)


class CaseResult(BaseModel):
    run_id: str
    case_id: str
    category: str
    query: str
    expected_output: str
    agent_output: str
    latency_ms: float
    score: float
    reasoning: str
    dimensions: dict[str, float] = Field(default_factory=dict)
    error: str | None = None


class EvaluationReport(BaseModel):
    id: str
    tenant_id: str
    run: EvaluationRun
    total_cases: int
    completed_cases: int
    average_score: float
    pass_rate: float
    average_latency_ms: float
    category_scores: dict[str, float]
    bad_cases: list[CaseResult]
    results: list[CaseResult]


class PingRequest(BaseModel):
    query: str = "ping"
    session_id: str = Field(default_factory=lambda: new_id("session"))


class PromptTemplate(BaseModel):
    category: str
    template: str


JsonDict = dict[str, Any]
Sentiment = Literal["positive", "negative", "neutral"]
