from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.ollama_client import MODEL_NAME, generate_response
from ..content.planning import (
    PlanningError,
    build_ideas_prompt,
    build_script_prompt,
    clean_script,
    evidence_summary,
    find_unsupported_numbers,
    parse_ideas,
)
from ..database import get_db
from ..models import ContentIdea, ContentScript, Evidence, Niche
from ..schemas import (
    IdeaCreate,
    IdeaGenerate,
    IdeaOut,
    IdeasResponse,
    ReviewNote,
    ScriptCreate,
    ScriptOut,
)

router = APIRouter()

ATTEMPTS = 2
AI_NOTE = (
    "AI-generated draft. It is not evidence, may contain mistakes, and nothing is approved "
    "until a human reviews it."
)


def _real_evidence(db: Session, niche_id: int) -> list[Evidence]:
    """Newest NON-demo evidence per criterion. Demo data never feeds content planning."""
    rows = db.scalars(
        select(Evidence)
        .where(Evidence.niche_id == niche_id, Evidence.is_demo.is_(False))
        .order_by(Evidence.observed_at)
    ).all()
    latest = {row.criterion: row for row in rows}
    return list(latest.values())


def _get_niche(db: Session, niche_id: int) -> Niche:
    niche = db.get(Niche, niche_id)
    if not niche:
        raise HTTPException(status_code=404, detail="Niche not found.")
    return niche


async def _ask_model(prompt: str, parse, json_mode: bool):
    """Call the model up to ATTEMPTS times; return parse(raw). Maps failures to HTTP errors."""
    last = "The model's answer was unusable."
    for _ in range(ATTEMPTS):
        try:
            raw = await generate_response(prompt, json_mode=json_mode)
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Ollama took too long to respond.")
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        try:
            return parse(raw)
        except PlanningError as exc:
            last = str(exc)
    raise HTTPException(status_code=502, detail=f"{last} Nothing was saved. Try again.")


def _decide(item, status: str, note: str | None):
    if item.status != "draft":
        raise HTTPException(status_code=409, detail=f"Already {item.status}. Decisions are final.")
    item.status = status
    item.reviewer_note = note
    item.reviewed_at = datetime.now(timezone.utc)


# ---------------- ideas ----------------

@router.post("/niches/{niche_id}/content/ideas/generate", response_model=IdeasResponse)
async def generate_ideas(niche_id: int, payload: IdeaGenerate, db: Session = Depends(get_db)):
    niche = _get_niche(db, niche_id)
    evidence = _real_evidence(db, niche_id)
    if not evidence:
        raise HTTPException(
            status_code=409,
            detail="Content planning needs approved, non-demo evidence for this niche first.",
        )
    summary = evidence_summary([(e.criterion, e.score, e.observation) for e in evidence])
    prompt = build_ideas_prompt(niche.name, summary, payload.count)
    parsed = await _ask_model(prompt, lambda raw: parse_ideas(raw, payload.count), json_mode=True)

    ideas = [ContentIdea(niche_id=niche_id, origin="ai_draft", status="draft", **item) for item in parsed]
    db.add_all(ideas)
    db.commit()
    for idea in ideas:
        db.refresh(idea)
    return IdeasResponse(model=MODEL_NAME, ideas=ideas, note=AI_NOTE)


@router.post("/niches/{niche_id}/content/ideas", response_model=IdeaOut, status_code=201)
def create_idea(niche_id: int, payload: IdeaCreate, db: Session = Depends(get_db)):
    """A human-written idea. The author is the human, so it starts approved."""
    _get_niche(db, niche_id)
    idea = ContentIdea(niche_id=niche_id, origin="human_entered", status="approved", **payload.model_dump())
    db.add(idea)
    db.commit()
    db.refresh(idea)
    return idea


@router.get("/content/ideas", response_model=list[IdeaOut])
def list_ideas(status: str | None = None, niche_id: int | None = None, db: Session = Depends(get_db)):
    query = select(ContentIdea).order_by(ContentIdea.id.desc())
    if status:
        query = query.where(ContentIdea.status == status)
    if niche_id:
        query = query.where(ContentIdea.niche_id == niche_id)
    return db.scalars(query).all()


def _idea(db: Session, idea_id: int) -> ContentIdea:
    idea = db.get(ContentIdea, idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found.")
    return idea


@router.post("/content/ideas/{idea_id}/approve", response_model=IdeaOut)
def approve_idea(idea_id: int, db: Session = Depends(get_db)):
    idea = _idea(db, idea_id)
    _decide(idea, "approved", None)
    db.commit()
    db.refresh(idea)
    return idea


@router.post("/content/ideas/{idea_id}/reject", response_model=IdeaOut)
def reject_idea(idea_id: int, payload: ReviewNote, db: Session = Depends(get_db)):
    idea = _idea(db, idea_id)
    _decide(idea, "rejected", payload.reviewer_note)
    db.commit()
    db.refresh(idea)
    return idea


# ---------------- scripts ----------------

@router.post("/content/ideas/{idea_id}/scripts/generate", response_model=ScriptOut)
async def generate_script(idea_id: int, db: Session = Depends(get_db)):
    idea = _idea(db, idea_id)
    if idea.status != "approved":
        raise HTTPException(status_code=409, detail="Scripts are written only for approved ideas.")
    niche = _get_niche(db, idea.niche_id)
    evidence = _real_evidence(db, idea.niche_id)
    if not evidence:
        raise HTTPException(
            status_code=409, detail="Script writing needs approved, non-demo evidence for this niche."
        )
    summary = evidence_summary([(e.criterion, e.score, e.observation) for e in evidence])
    prompt = build_script_prompt(niche.name, idea.title, idea.hook, idea.outline, summary)
    body = await _ask_model(prompt, clean_script, json_mode=False)

    allowed = " ".join([e.observation for e in evidence] + [idea.title, idea.hook, *idea.outline])
    script = ContentScript(
        idea_id=idea_id,
        body=body,
        origin="ai_draft",
        status="draft",
        unverified_numbers=find_unsupported_numbers(body, allowed),
    )
    db.add(script)
    db.commit()
    db.refresh(script)
    return script


@router.post("/content/ideas/{idea_id}/scripts", response_model=ScriptOut, status_code=201)
def create_script(idea_id: int, payload: ScriptCreate, db: Session = Depends(get_db)):
    """A human-written script. It starts approved because a human wrote it."""
    idea = _idea(db, idea_id)
    if idea.status != "approved":
        raise HTTPException(status_code=409, detail="Scripts are written only for approved ideas.")
    script = ContentScript(idea_id=idea_id, body=payload.body, origin="human_entered", status="approved")
    db.add(script)
    db.commit()
    db.refresh(script)
    return script


@router.get("/content/scripts", response_model=list[ScriptOut])
def list_scripts(status: str | None = None, idea_id: int | None = None, db: Session = Depends(get_db)):
    query = select(ContentScript).order_by(ContentScript.id.desc())
    if status:
        query = query.where(ContentScript.status == status)
    if idea_id:
        query = query.where(ContentScript.idea_id == idea_id)
    return db.scalars(query).all()


def _script(db: Session, script_id: int) -> ContentScript:
    script = db.get(ContentScript, script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found.")
    return script


@router.post("/content/scripts/{script_id}/approve", response_model=ScriptOut)
def approve_script(script_id: int, db: Session = Depends(get_db)):
    script = _script(db, script_id)
    _decide(script, "approved", None)
    db.commit()
    db.refresh(script)
    return script


@router.post("/content/scripts/{script_id}/reject", response_model=ScriptOut)
def reject_script(script_id: int, payload: ReviewNote, db: Session = Depends(get_db)):
    script = _script(db, script_id)
    _decide(script, "rejected", payload.reviewer_note)
    db.commit()
    db.refresh(script)
    return script
