from datetime import date, datetime, timezone
from sqlalchemy import String, Text, Float, Boolean, Date, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Niche(Base):
    __tablename__ = "niches"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    target_audience: Mapped[str] = mapped_column(Text, default="")
    platforms: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="candidate")
    latest_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_status: Mapped[str] = mapped_column(String(30), default="incomplete")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="niche", cascade="all, delete-orphan"
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"), index=True)
    criterion: Mapped[str] = mapped_column(String(50), index=True)
    score: Mapped[int] = mapped_column()
    confidence: Mapped[str] = mapped_column(String(20), default="low")
    observation: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    niche: Mapped["Niche"] = relationship(back_populates="evidence")



class EvidenceCandidate(Base):
    """A proposed piece of evidence awaiting human review. Not used in scoring until approved."""

    __tablename__ = "evidence_candidates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"), index=True)
    criterion: Mapped[str] = mapped_column(String(50), index=True)
    proposed_score: Mapped[int] = mapped_column()
    confidence: Mapped[str] = mapped_column(String(20), default="low")
    claim: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(1000))
    source_title: Mapped[str] = mapped_column(String(300), default="")
    publisher: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_published: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_excerpt: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(30), default="human_entered")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    # Result of the last machine check of source_excerpt against source_url:
    # not_checked | found | not_found | fetch_failed. A text match only; humans still decide.
    quote_check_status: Mapped[str] = mapped_column(
        String(20), default="not_checked", server_default="not_checked"
    )
    quote_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class ContentIdea(Base):
    """A proposed video idea. AI-generated ideas start as drafts and need human approval."""

    __tablename__ = "content_ideas"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    hook: Mapped[str] = mapped_column(Text, default="")
    outline: Mapped[list] = mapped_column(JSON, default=list)
    origin: Mapped[str] = mapped_column(String(30), default="ai_draft")  # ai_draft | human_entered
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft | approved | rejected
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ContentScript(Base):
    """A script for an approved idea. AI scripts start as drafts and need human approval."""

    __tablename__ = "content_scripts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    idea_id: Mapped[int] = mapped_column(ForeignKey("content_ideas.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(30), default="ai_draft")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    # Numbers in the script that appear nowhere in the niche's approved evidence.
    unverified_numbers: Mapped[list] = mapped_column(JSON, default=list)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ContentPost(Base):
    """One piece of content moving through a human-controlled publishing queue.

    planned -> ready (a human approves it for publishing) -> published (a human records the live URL)
    CreatorOS never posts anything itself: the person posts, then records it here.
    """

    __tablename__ = "content_posts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"), index=True)
    idea_id: Mapped[int | None] = mapped_column(ForeignKey("content_ideas.id"), nullable=True)
    script_id: Mapped[int | None] = mapped_column(ForeignKey("content_scripts.id"), nullable=True)
    platform: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="planned", index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    published_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PerformanceSnapshot(Base):
    """Cumulative totals for a published post on one date, as the platform shows them."""

    __tablename__ = "performance_snapshots"
    __table_args__ = (UniqueConstraint("post_id", "captured_on", name="uq_post_day"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("content_posts.id"), index=True)
    captured_on: Mapped[date] = mapped_column(Date)
    views: Mapped[int] = mapped_column(default=0)
    likes: Mapped[int] = mapped_column(default=0)
    comments: Mapped[int] = mapped_column(default=0)
    watch_time_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    followers_gained: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MoneyEntry(Base):
    """Money in or out, in whole minor units (cents). Never mixed across currencies."""

    __tablename__ = "money_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"), index=True)
    post_id: Mapped[int | None] = mapped_column(ForeignKey("content_posts.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(10))  # revenue | cost
    source: Mapped[str] = mapped_column(String(30))
    amount_cents: Mapped[int] = mapped_column()
    currency: Mapped[str] = mapped_column(String(3))
    occurred_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
