from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class RoleEnum(str, Enum):
    guest = "guest"
    analyst = "analyst"
    researcher = "researcher"
    data_steward = "data_steward"
    admin = "admin"


class PurposeEnum(str, Enum):
    research = "research"
    commercial = "commercial"
    planning = "planning"
    internal_audit = "internal_audit"


class StrategyEnum(str, Enum):
    balanced = "balanced"
    cheapest = "cheapest"
    trust_first = "trust_first"
    privacy_first = "privacy_first"


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=5, max_length=1000, description="SQL-like query over a virtual dataset")
    role: RoleEnum = Field(RoleEnum.researcher, description="User role")
    purpose: PurposeEnum = Field(PurposeEnum.research, description="Query purpose")
    strategy: StrategyEnum = Field(StrategyEnum.balanced, description="Optimisation strategy")
    verification: bool = Field(False, description="Force multi-source verification")
    show_all_conflicts: bool = Field(False, description="Return provenance and conflict details when verification is requested")

    @field_validator("query")
    @classmethod
    def query_must_be_select(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Query must be a non-empty string")
        if not v.strip().upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are supported")
        return v


class QueryResponse(BaseModel):
    ok: bool
    message: str
    parsed_query: Optional[Dict[str, Any]] = None
    policy_decision: Dict[str, Any] = Field(default_factory=dict)
    selected_plan: Dict[str, Any] = Field(default_factory=dict)
    candidate_plans: List[Dict[str, Any]] = Field(default_factory=list)
    result_rows: List[Dict[str, Any]] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    pricing: Dict[str, Any] = Field(default_factory=dict)
    execution_metrics: Dict[str, Any] = Field(default_factory=dict)
    audit_id: Optional[str] = None


@dataclass
class ParsedPredicate:
    left: str
    op: str
    right: str
    right_is_column: bool = False


@dataclass
class ParsedQuery:
    raw: str
    select: List[str]
    dataset: str
    where: Optional[ParsedPredicate] = None
    join_dataset: Optional[str] = None
    join_left: Optional[str] = None
    join_right: Optional[str] = None
    verification_hint: bool = False
    limit: Optional[int] = None
    order_by: Optional[str] = None
    order_dir: str = "asc"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw": self.raw,
            "select": self.select,
            "dataset": self.dataset,
            "where": self.where.__dict__ if self.where else None,
            "join_dataset": self.join_dataset,
            "join_left": self.join_left,
            "join_right": self.join_right,
            "verification_hint": self.verification_hint,
            "limit": self.limit,
            "order_by": self.order_by,
            "order_dir": self.order_dir,
        }


@dataclass
class SourcePlanEstimate:
    source_name: str
    dataset: str
    estimated_rows_scanned: int
    estimated_rows_returned: int
    estimated_latency_ms: float
    estimated_execution_cost: float
    api_calls: int
    trust_score: float
    freshness_score: float
    conflict_risk: float
    supported_columns: List[str]
    explanation: str


@dataclass
class CandidatePlan:
    plan_id: str
    mode: str
    strategy: str
    datasets: List[str]
    sources: List[str]
    source_estimates: List[SourcePlanEstimate]
    estimated_rows_scanned: int
    estimated_rows_returned: int
    estimated_latency_ms: float
    estimated_execution_cost: float
    api_calls: int
    mean_trust: float
    mean_freshness: float
    conflict_risk: float
    optimiser_score: float
    complexity_class: str
    explanation: str
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "mode": self.mode,
            "strategy": self.strategy,
            "datasets": self.datasets,
            "sources": self.sources,
            "source_estimates": [s.__dict__ for s in self.source_estimates],
            "estimated_rows_scanned": self.estimated_rows_scanned,
            "estimated_rows_returned": self.estimated_rows_returned,
            "estimated_latency_ms": round(self.estimated_latency_ms, 2),
            "estimated_execution_cost": round(self.estimated_execution_cost, 4),
            "api_calls": self.api_calls,
            "mean_trust": round(self.mean_trust, 4),
            "mean_freshness": round(self.mean_freshness, 4),
            "conflict_risk": round(self.conflict_risk, 4),
            "optimiser_score": round(self.optimiser_score, 4),
            "complexity_class": self.complexity_class,
            "explanation": self.explanation,
            "warnings": self.warnings,
        }


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1, max_length=256)


class NewPasswordRequest(BaseModel):
    session: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=6, max_length=256)
    email: Optional[str] = Field(default=None, max_length=320)




class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)


class ConfirmForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    confirmation_code: str = Field(..., min_length=3, max_length=256)
    new_password: str = Field(..., min_length=6, max_length=256)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=256)
    new_password: str = Field(..., min_length=6, max_length=256)


class AdminCreateUserRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    temp_password: str = Field(..., min_length=6, max_length=256)
    role: RoleEnum = Field(RoleEnum.researcher)
    name: Optional[str] = Field(default=None, max_length=120)
