from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

Criterion = Literal[
    "audience_demand",
    "monetization_potential",
    "affiliate_opportunities",
    "competition_accessibility",
    "production_feasibility",
    "long_term_demand",
    "creator_capability",
]


class NicheCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = ""
    target_audience: str = ""
    platforms: list[str] = ["YouTube", "Instagram"]
    status: Literal["candidate", "testing", "approved", "rejected"] = "candidate"


class NicheOut(BaseModel):
    id: int
    name: str
    description: str
    target_audience: str
    platforms: list
    status: str
    latest_score: float | None
    score_status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EvidenceCreate(BaseModel):
    criterion: Criterion
    score: int = Field(ge=1, le=10)
    confidence: Literal["low", "medium", "high"] = "low"
    observation: str = Field(min_length=10, max_length=5000)
    source_url: str | None = Field(default=None, max_length=1000)
    is_demo: bool = False


class EvidenceOut(BaseModel):
    id: int
    niche_id: int
    criterion: str
    score: int
    confidence: str
    observation: str
    source_url: str | None
    is_demo: bool
    observed_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EvaluationOut(BaseModel):
    niche_id: int
    niche_name: str
    status: str
    weighted_score: float | None
    criteria_present: list[str]
    criteria_missing: list[str]
    breakdown: dict[str, dict]
    contains_demo_evidence: bool
    interpretation: str
