from datetime import datetime, timezone
from sqlalchemy import String, Text, Float, Boolean, DateTime, ForeignKey, JSON
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)