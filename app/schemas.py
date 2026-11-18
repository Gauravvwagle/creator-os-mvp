from datetime import date, datetime
from decimal import Decimal
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
    quote_check_status: str
    quote_checked_at: datetime | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CandidateApprove(BaseModel):
    reviewer_note: str = Field(default="", max_length=2000)


class CandidateReject(BaseModel):
    reviewer_note: str = Field(min_length=3, max_length=2000)

# ---------- content planning ----------

class ReviewNote(BaseModel):
    reviewer_note: str = Field(min_length=3, max_length=2000)


class IdeaGenerate(BaseModel):
    count: int = Field(default=3, ge=1, le=5)


class IdeaCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    hook: str = Field(default="", max_length=500)
    outline: list[str] = Field(default_factory=list, max_length=8)


class IdeaOut(BaseModel):
    id: int
    niche_id: int
    title: str
    hook: str
    outline: list[str]
    origin: str
    status: str
    reviewer_note: str | None
    reviewed_at: datetime | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IdeasResponse(BaseModel):
    model: str
    ideas: list[IdeaOut]
    note: str


class ScriptCreate(BaseModel):
    body: str = Field(min_length=20, max_length=20000)


class ScriptOut(BaseModel):
    id: int
    idea_id: int
    body: str
    origin: str
    status: str
    unverified_numbers: list[str]
    reviewer_note: str | None
    reviewed_at: datetime | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------- publishing queue, performance, money ----------

Platform = Literal["youtube", "instagram", "tiktok", "other"]
MoneySource = Literal["adsense", "affiliate", "sponsorship", "product", "tool", "ads_spend", "other"]


class PostCreate(BaseModel):
    platform: Platform
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    idea_id: int | None = None
    script_id: int | None = None


class PostOut(BaseModel):
    id: int
    niche_id: int
    idea_id: int | None
    script_id: int | None
    platform: str
    title: str
    description: str
    tags: list[str]
    status: str
    approved_at: datetime | None
    url: str | None
    published_on: date | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PostPublished(BaseModel):
    url: HttpUrl
    published_on: date | None = None  # defaults to today


class PostPackage(BaseModel):
    post_id: int
    platform: str
    text: str
    reminders: list[str]


class PerformanceIn(BaseModel):
    captured_on: date | None = None  # defaults to today
    views: int = Field(ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    watch_time_minutes: float = Field(default=0, ge=0)
    followers_gained: int = Field(default=0, ge=0)


class PerformanceOut(BaseModel):
    id: int
    post_id: int
    captured_on: date
    views: int
    likes: int
    comments: int
    watch_time_minutes: float
    followers_gained: int
    model_config = ConfigDict(from_attributes=True)


class MoneyIn(BaseModel):
    kind: Literal["revenue", "cost"]
    source: MoneySource
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3, pattern="^[A-Za-z]{3}$")
    occurred_on: date | None = None  # defaults to today
    post_id: int | None = None
    note: str = Field(default="", max_length=1000)


class MoneyOut(BaseModel):
    id: int
    niche_id: int
    post_id: int | None
    kind: str
    source: str
    amount: str
    amount_cents: int
    currency: str
    occurred_on: date
    note: str
