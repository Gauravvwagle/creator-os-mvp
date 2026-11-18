from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.ollama_client import MODEL_NAME, generate_response
from ..database import get_db
from ..models import EvidenceCandidate, Niche
from ..research.fetcher import FetchError, fetch_page_text
from ..research.suggest import (
    NoUsefulSentence,
    SuggestionError,
    build_suggestion_prompt,
    parse_suggestion,
    pick_relevant,
    split_sentences,
)
from ..schemas import CandidateOut, Criterion
from ..scoring import WEIGHTS

router = APIRouter()

ATTEMPTS = 2  # a small local model sometimes returns unusable output; try once more
AI_CLAIM_PREFIX = "[AI draft] "


class SuggestRequest(BaseModel):
    url: HttpUrl
    criteria: list[Criterion] | None = Field(
        default=None, max_length=7, description="Defaults to all seven criteria."
    )


class Skipped(BaseModel):
    criterion: str
    reason: str


class SuggestResponse(BaseModel):
    model: str
    source_title: str
    candidates: list[CandidateOut]
    skipped: list[Skipped]
    note: str


@router.post("/niches/{niche_id}/candidates/suggest", response_model=SuggestResponse)
async def suggest_candidates(niche_id: int, payload: SuggestRequest, db: Session = Depends(get_db)):
    """Read ONE page and file pending candidates for a human to review.

    Automated up to the review gate: nothing here is approved, scored or counted as evidence.
    The excerpt is copied by code from the page; the model only picks the sentence number and
    drafts a claim and score.
    """
    niche = db.get(Niche, niche_id)
    if not niche:
        raise HTTPException(status_code=404, detail="Niche not found.")

    url = str(payload.url)
    try:
        page = await fetch_page_text(url)
    except FetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    sentences = split_sentences(page["text"])
    if not sentences:
        raise HTTPException(status_code=422, detail="The page has no usable sentences to choose from.")

    criteria = list(dict.fromkeys(payload.criteria or WEIGHTS.keys()))
    created: list[EvidenceCandidate] = []
    skipped: list[Skipped] = []

    for criterion in criteria:
        choices = pick_relevant(sentences, niche.name, criterion)
        prompt = build_suggestion_prompt(niche.name, criterion, choices)

        suggestion, failure = None, "The model's answer was unusable."
        for _ in range(ATTEMPTS):
            try:
                raw = await generate_response(prompt, json_mode=True)
            except (httpx.TimeoutException, RuntimeError) as exc:
                if not created and not skipped:
                    # Ollama is not working at all: fail clearly instead of returning nothing.
                    if isinstance(exc, httpx.TimeoutException):
                        raise HTTPException(status_code=504, detail="Ollama took too long to respond.")
                    raise HTTPException(status_code=503, detail=str(exc))
                skipped.append(Skipped(criterion=criterion, reason="Ollama stopped responding."))
                suggestion, failure = None, None
                break
            try:
                suggestion = parse_suggestion(raw, len(choices))
                break
            except NoUsefulSentence as exc:
                failure = str(exc)
                break
            except SuggestionError as exc:
                failure = str(exc)

        if failure is None:  # Ollama stopped; remaining criteria would fail the same way
            break
        if suggestion is None:
            skipped.append(Skipped(criterion=criterion, reason=failure))
            continue

        excerpt = choices[suggestion["index"]]  # copied by code, never written by the model
        duplicate = db.scalar(
            select(EvidenceCandidate.id).where(
                EvidenceCandidate.niche_id == niche_id,
                EvidenceCandidate.criterion == criterion,
                EvidenceCandidate.source_url == page["final_url"],
                EvidenceCandidate.source_excerpt == excerpt,
            )
        )
        if duplicate:
            skipped.append(Skipped(criterion=criterion, reason="Already suggested for this page."))
            continue

        candidate = EvidenceCandidate(
            niche_id=niche_id,
            criterion=criterion,
            proposed_score=suggestion["score"],
            confidence="low",  # a model's judgement is never high confidence by itself
            claim=AI_CLAIM_PREFIX + suggestion["claim"],
            source_url=page["final_url"],
            source_title=(page["title"] or "")[:300],
            source_excerpt=excerpt,
            origin="ai_suggested",
            status="pending",
            # The excerpt was copied from this page's text a moment ago, so it is found by construction.
            quote_check_status="found",
            quote_checked_at=datetime.now(timezone.utc),
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        created.append(candidate)

    return SuggestResponse(
        model=MODEL_NAME,
        source_title=page["title"] or "",
        candidates=created,
        skipped=skipped,
        note=(
            "AI-suggested drafts. The excerpt is copied verbatim from the page, but the claim and "
            "score are model drafts and may be wrong or misleading. Nothing is approved or scored "
            "until a human reviews it."
        ),
    )
