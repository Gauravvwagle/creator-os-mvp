from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import (
    ContentIdea,
    ContentPost,
    ContentScript,
    MoneyEntry,
    Niche,
    PerformanceSnapshot,
)
from ..schemas import (
    MoneyIn,
    MoneyOut,
    PerformanceIn,
    PerformanceOut,
    PostCreate,
    PostOut,
    PostPackage,
    PostPublished,
)
from ..scoring import evaluate_evidence

router = APIRouter()

MIN_POSTS_FOR_CONCLUSIONS = 5
REVENUE_SOURCES = {"adsense", "affiliate", "sponsorship", "product", "other"}
COST_SOURCES = {"tool", "ads_spend", "other"}


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _not_future(value: date, label: str) -> date:
    if value > _today():
        raise HTTPException(status_code=422, detail=f"{label} cannot be in the future.")
    return value


def _niche(db: Session, niche_id: int) -> Niche:
    niche = db.get(Niche, niche_id)
    if not niche:
        raise HTTPException(status_code=404, detail="Niche not found.")
    return niche


def _post(db: Session, post_id: int) -> ContentPost:
    post = db.get(ContentPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
    return post


# ---------------- publishing queue ----------------

@router.post("/niches/{niche_id}/posts", response_model=PostOut, status_code=201)
def create_post(niche_id: int, payload: PostCreate, db: Session = Depends(get_db)):
    _niche(db, niche_id)
    idea_id = payload.idea_id
    if payload.script_id is not None:
        script = db.get(ContentScript, payload.script_id)
        if not script:
            raise HTTPException(status_code=404, detail="Script not found.")
        if script.status != "approved":
            raise HTTPException(status_code=409, detail="Only an approved script can be queued for publishing.")
        if idea_id is not None and idea_id != script.idea_id:
            raise HTTPException(status_code=422, detail="That script belongs to a different idea.")
        idea_id = script.idea_id
    if idea_id is not None:
        idea = db.get(ContentIdea, idea_id)
        if not idea:
            raise HTTPException(status_code=404, detail="Idea not found.")
        if idea.niche_id != niche_id:
            raise HTTPException(status_code=422, detail="That idea belongs to a different niche.")
        if idea.status != "approved":
            raise HTTPException(status_code=409, detail="Only an approved idea can be queued for publishing.")

    post = ContentPost(
        niche_id=niche_id,
        idea_id=idea_id,
        script_id=payload.script_id,
        platform=payload.platform,
        title=payload.title,
        description=payload.description,
        tags=[t.strip() for t in payload.tags if t.strip()],
        status="planned",
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.get("/posts", response_model=list[PostOut])
def list_posts(status: str | None = None, niche_id: int | None = None, db: Session = Depends(get_db)):
    query = select(ContentPost).order_by(ContentPost.id.desc())
    if status:
        query = query.where(ContentPost.status == status)
    if niche_id:
        query = query.where(ContentPost.niche_id == niche_id)
    return db.scalars(query).all()


@router.post("/posts/{post_id}/approve", response_model=PostOut)
def approve_post(post_id: int, db: Session = Depends(get_db)):
    """A human approves the post for publishing. Nothing is posted by CreatorOS."""
    post = _post(db, post_id)
    if post.status != "planned":
        raise HTTPException(status_code=409, detail=f"Only a planned post can be approved (this one is {post.status}).")
    post.status = "ready"
    post.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(post)
    return post


@router.get("/posts/{post_id}/package", response_model=PostPackage)
def post_package(post_id: int, db: Session = Depends(get_db)):
    """Everything needed to post by hand: title, description, tags and the script."""
    post = _post(db, post_id)
    if post.status not in {"ready", "published"}:
        raise HTTPException(status_code=409, detail="Approve the post for publishing first.")
    script = db.get(ContentScript, post.script_id) if post.script_id else None

    parts = [f"TITLE\n{post.title}", f"DESCRIPTION\n{post.description or '(none)'}"]
    parts.append("TAGS\n" + (", ".join(post.tags) if post.tags else "(none)"))
    if script:
        parts.append(f"SCRIPT\n{script.body}")

    reminders = [
        "CreatorOS does not post for you. Post it yourself, then record the live link here.",
        "Check the platform's current rules on sponsored content, affiliate links and AI-generated or AI-assisted content before posting.",
        "Do not promise earnings or results.",
    ]
    if script and script.unverified_numbers:
        reminders.append(
            "This script contains numbers that appear nowhere in your approved evidence: "
            + ", ".join(script.unverified_numbers) + ". Check each one or remove it."
        )
    return PostPackage(post_id=post.id, platform=post.platform, text="\n\n".join(parts), reminders=reminders)


@router.post("/posts/{post_id}/published", response_model=PostOut)
def mark_published(post_id: int, payload: PostPublished, db: Session = Depends(get_db)):
    """A human records that the post is live, with its link."""
    post = _post(db, post_id)
    if post.status != "ready":
        raise HTTPException(status_code=409, detail=f"Only a post that is ready can be marked published (this one is {post.status}).")
    post.status = "published"
    post.url = str(payload.url)
    post.published_on = _not_future(payload.published_on or _today(), "published_on")
    db.commit()
    db.refresh(post)
    return post


@router.post("/posts/{post_id}/cancel", response_model=PostOut)
def cancel_post(post_id: int, db: Session = Depends(get_db)):
    post = _post(db, post_id)
    if post.status not in {"planned", "ready"}:
        raise HTTPException(status_code=409, detail=f"A {post.status} post cannot be cancelled.")
    post.status = "cancelled"
    db.commit()
    db.refresh(post)
    return post


# ---------------- performance ----------------

@router.post("/posts/{post_id}/performance", response_model=PerformanceOut)
def record_performance(post_id: int, payload: PerformanceIn, db: Session = Depends(get_db)):
    """Record cumulative totals as the platform shows them. One entry per day; re-sending a day replaces it."""
    post = _post(db, post_id)
    if post.status != "published":
        raise HTTPException(status_code=409, detail="Performance can only be recorded for a published post.")
    captured = _not_future(payload.captured_on or _today(), "captured_on")
    if post.published_on and captured < post.published_on:
        raise HTTPException(status_code=422, detail="captured_on is before the post was published.")

    snapshot = db.scalar(
        select(PerformanceSnapshot).where(
            PerformanceSnapshot.post_id == post_id, PerformanceSnapshot.captured_on == captured
        )
    )
    if snapshot is None:
        snapshot = PerformanceSnapshot(post_id=post_id, captured_on=captured)
        db.add(snapshot)
    snapshot.views = payload.views
    snapshot.likes = payload.likes
    snapshot.comments = payload.comments
    snapshot.watch_time_minutes = payload.watch_time_minutes
    snapshot.followers_gained = payload.followers_gained
    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.get("/posts/{post_id}/performance", response_model=list[PerformanceOut])
def list_performance(post_id: int, db: Session = Depends(get_db)):
    _post(db, post_id)
    return db.scalars(
        select(PerformanceSnapshot).where(PerformanceSnapshot.post_id == post_id).order_by(PerformanceSnapshot.captured_on)
    ).all()


# ---------------- money ----------------

def _money_out(entry: MoneyEntry) -> MoneyOut:
    return MoneyOut(
        id=entry.id, niche_id=entry.niche_id, post_id=entry.post_id, kind=entry.kind, source=entry.source,
        amount=_fmt(entry.amount_cents), amount_cents=entry.amount_cents, currency=entry.currency,
        occurred_on=entry.occurred_on, note=entry.note,
    )


def _fmt(cents: int) -> str:
    return str((Decimal(cents) / 100).quantize(Decimal("0.01")))


@router.post("/niches/{niche_id}/money", response_model=MoneyOut, status_code=201)
def add_money(niche_id: int, payload: MoneyIn, db: Session = Depends(get_db)):
    _niche(db, niche_id)
    allowed = REVENUE_SOURCES if payload.kind == "revenue" else COST_SOURCES
    if payload.source not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"A {payload.kind} cannot have source '{payload.source}'. Use one of: {', '.join(sorted(allowed))}.",
        )
    if payload.post_id is not None:
        post = db.get(ContentPost, payload.post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found.")
        if post.niche_id != niche_id:
            raise HTTPException(status_code=422, detail="That post belongs to a different niche.")
        if post.status != "published":
            raise HTTPException(status_code=409, detail="Money can only be linked to a published post.")

    entry = MoneyEntry(
        niche_id=niche_id,
        post_id=payload.post_id,
        kind=payload.kind,
        source=payload.source,
        amount_cents=int((payload.amount * 100).to_integral_value()),
        currency=payload.currency.upper(),
        occurred_on=_not_future(payload.occurred_on or _today(), "occurred_on"),
        note=payload.note,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _money_out(entry)


@router.get("/niches/{niche_id}/money", response_model=list[MoneyOut])
def list_money(niche_id: int, db: Session = Depends(get_db)):
    _niche(db, niche_id)
    entries = db.scalars(
        select(MoneyEntry).where(MoneyEntry.niche_id == niche_id).order_by(MoneyEntry.occurred_on.desc(), MoneyEntry.id.desc())
    ).all()
    return [_money_out(e) for e in entries]


@router.delete("/money/{entry_id}", status_code=204)
def delete_money(entry_id: int, db: Session = Depends(get_db)):
    """Remove a mistaken entry."""
    entry = db.get(MoneyEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found.")
    db.delete(entry)
    db.commit()


# ---------------- outcomes report ----------------

@router.get("/reports/outcomes")
def outcomes(db: Session = Depends(get_db)):
    """Compare each niche's research score with what actually happened after publishing."""
    niches = db.scalars(select(Niche).options(selectinload(Niche.evidence))).all()
    rows = []
    for niche in niches:
        result = evaluate_evidence(niche.evidence)
        posts = db.scalars(
            select(ContentPost).where(ContentPost.niche_id == niche.id, ContentPost.status == "published")
        ).all()

        views = likes = comments = followers = measured = 0
        for post in posts:
            latest = db.scalars(
                select(PerformanceSnapshot)
                .where(PerformanceSnapshot.post_id == post.id)
                .order_by(PerformanceSnapshot.captured_on.desc())
                .limit(1)
            ).first()
            if latest:  # snapshots are cumulative, so use only the newest one per post
                measured += 1
                views += latest.views
                likes += latest.likes
                comments += latest.comments
                followers += latest.followers_gained

        money: dict[str, dict[str, int]] = defaultdict(lambda: {"revenue_cents": 0, "cost_cents": 0})
        for entry in db.scalars(select(MoneyEntry).where(MoneyEntry.niche_id == niche.id)).all():
            money[entry.currency]["revenue_cents" if entry.kind == "revenue" else "cost_cents"] += entry.amount_cents
        money_out = {
            currency: {
                "revenue": _fmt(t["revenue_cents"]),
                "cost": _fmt(t["cost_cents"]),
                "net": _fmt(t["revenue_cents"] - t["cost_cents"]),
            }
            for currency, t in sorted(money.items())
        }

        enough = len(posts) >= MIN_POSTS_FOR_CONCLUSIONS
        rows.append({
            "niche_id": niche.id,
            "niche_name": niche.name,
            "research_status": result["status"],
            "research_score": result["weighted_score"],
            "contains_demo_evidence": result["contains_demo_evidence"],
            "posts_published": len(posts),
            "posts_with_performance": measured,
            "total_views": views,
            "avg_views_per_measured_post": round(views / measured, 1) if measured else None,
            "engagement_rate": round((likes + comments) / views, 4) if views else None,
            "followers_gained": followers,
            "money": money_out,
            "enough_data": enough,
            "data_note": (
                "Enough posts to start comparing, but still treat this as a hint."
                if enough
                else f"Only {len(posts)} published post(s): too few to judge whether the research score predicts results (need at least {MIN_POSTS_FOR_CONCLUSIONS})."
            ),
        })
    rows.sort(key=lambda r: (-r["posts_published"], r["niche_name"]))
    return {
        "note": (
            "Performance figures are cumulative totals you entered by hand. Money is shown per currency "
            "with no conversion. Research scores are decision support, not forecasts."
        ),
        "niches": rows,
    }
