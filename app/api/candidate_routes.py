from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Niche, Evidence, EvidenceCandidate
from ..schemas import CandidateCreate, CandidateOut, CandidateApprove, CandidateReject

router = APIRouter()


def _get_pending(candidate_id: int, db: Session) -> EvidenceCandidate:
    candidate = db.get(EvidenceCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if candidate.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Candidate was already {candidate.status}. Decisions are final.",
        )
    return candidate


def _build_observation(c: EvidenceCandidate) -> str:
    parts = [
        c.claim,
        f"Source excerpt: {c.source_excerpt}",
        f"Source: {c.source_title or c.source_url}",
    ]
    if c.publisher:
        parts.append(f"Publisher: {c.publisher}")
    if c.source_published:
        parts.append(f"Published/updated: {c.source_published}")
    parts.append(f"Captured: {c.created_at.date().isoformat()}")
    parts.append("Human-reviewed and approved.")
    return "\n\n".join(parts)


@router.post(
    "/niches/{niche_id}/candidates", response_model=CandidateOut, status_code=201
)
def create_candidate(
    niche_id: int, payload: CandidateCreate, db: Session = Depends(get_db)
):
    if not db.get(Niche, niche_id):
        raise HTTPException(status_code=404, detail="Niche not found.")
    data = payload.model_dump()
    data["source_url"] = str(payload.source_url)
    candidate = EvidenceCandidate(niche_id=niche_id, status="pending", **data)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.get("/candidates", response_model=list[CandidateOut])
def list_candidates(
    status: Literal["pending", "approved", "rejected"] = "pending",
    niche_id: int | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(EvidenceCandidate).where(EvidenceCandidate.status == status)
    if niche_id is not None:
        stmt = stmt.where(EvidenceCandidate.niche_id == niche_id)
    stmt = stmt.order_by(EvidenceCandidate.created_at.desc())
    return list(db.scalars(stmt).all())


@router.post("/candidates/{candidate_id}/approve", response_model=CandidateOut)
def approve_candidate(
    candidate_id: int,
    payload: CandidateApprove,
    db: Session = Depends(get_db),
):
    candidate = _get_pending(candidate_id, db)
    niche = db.get(Niche, candidate.niche_id)

    evidence = Evidence(
        niche_id=candidate.niche_id,
        criterion=candidate.criterion,
        score=candidate.proposed_score,
        confidence=candidate.confidence,
        observation=_build_observation(candidate),
        source_url=candidate.source_url,
        is_demo=False,
    )
    db.add(evidence)
    db.flush()  # assigns evidence.id

    candidate.status = "approved"
    candidate.reviewer_note = payload.reviewer_note or None
    candidate.reviewed_at = datetime.now(timezone.utc)
    candidate.evidence_id = evidence.id

    # Same rule as add_evidence: new evidence invalidates the old score.
    niche.score_status = "incomplete"
    niche.latest_score = None

    db.commit()
    db.refresh(candidate)
    return candidate


@router.post("/candidates/{candidate_id}/reject", response_model=CandidateOut)
def reject_candidate(
    candidate_id: int,
    payload: CandidateReject,
    db: Session = Depends(get_db),
):
    candidate = _get_pending(candidate_id, db)
    candidate.status = "rejected"
    candidate.reviewer_note = payload.reviewer_note
    candidate.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(candidate)
    return candidate