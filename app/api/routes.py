from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select
from ..database import get_db
from ..models import Niche, Evidence
from ..schemas import NicheCreate, NicheOut, EvidenceCreate, EvidenceOut, EvaluationOut
from ..scoring import evaluate_evidence

router = APIRouter()


@router.post("/niches", response_model=NicheOut, status_code=201)
def create_niche(payload: NicheCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(Niche).where(Niche.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="A niche with this name already exists.")
    niche = Niche(**payload.model_dump())
    db.add(niche)
    db.commit()
    db.refresh(niche)
    return niche


@router.get("/niches", response_model=list[NicheOut])
def list_niches(db: Session = Depends(get_db)):
    return list(db.scalars(select(Niche).order_by(Niche.created_at.desc())).all())


@router.get("/niches/{niche_id}")
def get_niche(niche_id: int, db: Session = Depends(get_db)):
    niche = db.scalar(
        select(Niche).options(selectinload(Niche.evidence)).where(Niche.id == niche_id)
    )
    if not niche:
        raise HTTPException(status_code=404, detail="Niche not found.")
    return {
        "niche": NicheOut.model_validate(niche),
        "evidence": [EvidenceOut.model_validate(x) for x in niche.evidence],
    }


@router.post("/niches/{niche_id}/evidence", response_model=EvidenceOut, status_code=201)
def add_evidence(niche_id: int, payload: EvidenceCreate, db: Session = Depends(get_db)):
    niche = db.get(Niche, niche_id)
    if not niche:
        raise HTTPException(status_code=404, detail="Niche not found.")
    item = Evidence(niche_id=niche_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    # Any new evidence invalidates the previous evaluation until re-evaluated.
    niche.score_status = "incomplete"
    niche.latest_score = None
    db.commit()
    return item


@router.post("/niches/{niche_id}/evaluate", response_model=EvaluationOut)
def evaluate_niche(niche_id: int, db: Session = Depends(get_db)):
    niche = db.scalar(
        select(Niche).options(selectinload(Niche.evidence)).where(Niche.id == niche_id)
    )
    if not niche:
        raise HTTPException(status_code=404, detail="Niche not found.")
    result = evaluate_evidence(niche.evidence)
    niche.score_status = result["status"]
    niche.latest_score = result["weighted_score"]
    db.commit()
    return {
        "niche_id": niche.id,
        "niche_name": niche.name,
        **result,
    }


@router.get("/reports/rankings")
def rankings(db: Session = Depends(get_db)):
    niches = db.scalars(
        select(Niche).options(selectinload(Niche.evidence))
    ).all()
    rows = []
    for niche in niches:
        result = evaluate_evidence(niche.evidence)
        rows.append({
            "niche_id": niche.id,
            "niche_name": niche.name,
            "status": result["status"],
            "weighted_score": result["weighted_score"],
            "contains_demo_evidence": result["contains_demo_evidence"],
            "criteria_missing": result["criteria_missing"],
            "interpretation": result["interpretation"],
        })
    ranked = sorted(
        [x for x in rows if x["status"] == "evaluated"],
        key=lambda x: x["weighted_score"],
        reverse=True,
    )
    incomplete = [x for x in rows if x["status"] != "evaluated"]
    return {
        "ranking_note": "Scores are evidence-based decision support, not revenue forecasts. Demo evidence is not suitable for business decisions.",
        "ranked": ranked,
        "incomplete": incomplete,
    }
