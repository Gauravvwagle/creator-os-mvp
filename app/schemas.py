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



class CandidateCreate(BaseModel):
    criterion: Criterion
    proposed_score: int = Field(ge=1, le=10)
    confidence: Literal["low", "medium", "high"] = "low"
    claim: str = Field(min_length=10, max_length=2000)
    source_url: HttpUrl
    source_title: str = Field(default="", max_length=300)
    publisher: str | None = Field(default=None, max_length=200)
    source_published: str | None = Field(default=None, max_length=100)
    source_excerpt: str = Field(min_length=10, max_length=3000)
    origin: Literal["human_entered", "ai_suggested"] = "human_entered"


class CandidateOut(BaseModel):
    id: int
    niche_id: int
    criterion: str
    proposed_score: int
    confidence: str
    claim: str
    source_url: str
    source_title: str
    publisher: str | None
    source_published: str | None
    source_excerpt: str
    origin: str
    status: str
    reviewer_note: str | None
    reviewed_at: datetime | None
    evidence_id: int | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CandidateApprove(BaseModel):
    reviewer_note: str = Field(default="", max_length=2000)


class CandidateReject(BaseModel):
    reviewer_note: str = Field(min_length=3, max_length=2000)