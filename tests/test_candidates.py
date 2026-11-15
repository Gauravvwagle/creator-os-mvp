import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app import models  # noqa: F401  (registers tables on Base)
from app.api.routes import router
from app.api.candidate_routes import router as candidate_router

CRITERIA = [
    "audience_demand",
    "monetization_potential",
    "affiliate_opportunities",
    "competition_accessibility",
    "production_feasibility",
    "long_term_demand",
    "creator_capability",
]


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.include_router(candidate_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c


def make_niche(client, name="Test Niche"):
    r = client.post("/api/v1/niches", json={"name": name})
    assert r.status_code == 201
    return r.json()["id"]


def candidate_payload(**overrides):
    data = {
        "criterion": "affiliate_opportunities",
        "proposed_score": 6,
        "confidence": "low",
        "claim": "TEST ONLY: placeholder claim for testing.",
        "source_url": "https://example.com/test",
        "source_title": "Test page",
        "source_excerpt": "TEST ONLY: placeholder excerpt for testing.",
    }
    data.update(overrides)
    return data


def create_candidate(client, niche_id, **overrides):
    r = client.post(
        f"/api/v1/niches/{niche_id}/candidates", json=candidate_payload(**overrides)
    )
    assert r.status_code == 201, r.text
    return r.json()


def evidence_for(client, niche_id):
    return client.get(f"/api/v1/niches/{niche_id}").json()["evidence"]


def test_new_candidate_is_pending_and_creates_no_evidence(client):
    niche_id = make_niche(client)
    cand = create_candidate(client, niche_id)
    assert cand["status"] == "pending"
    assert cand["evidence_id"] is None
    assert evidence_for(client, niche_id) == []


def test_candidate_requires_source_excerpt(client):
    niche_id = make_niche(client)
    payload = candidate_payload()
    del payload["source_excerpt"]
    r = client.post(f"/api/v1/niches/{niche_id}/candidates", json=payload)
    assert r.status_code == 422


def test_candidate_requires_valid_url(client):
    niche_id = make_niche(client)
    r = client.post(
        f"/api/v1/niches/{niche_id}/candidates",
        json=candidate_payload(source_url="not a url"),
    )
    assert r.status_code == 422


def test_candidate_for_unknown_niche_returns_404(client):
    r = client.post("/api/v1/niches/9999/candidates", json=candidate_payload())
    assert r.status_code == 404


def test_approve_creates_evidence_with_source(client):
    niche_id = make_niche(client)
    cand = create_candidate(client, niche_id)
    r = client.post(f"/api/v1/candidates/{cand['id']}/approve", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "approved"
    assert body["evidence_id"] is not None
    assert body["reviewed_at"] is not None

    evidence = evidence_for(client, niche_id)
    assert len(evidence) == 1
    assert evidence[0]["source_url"] == "https://example.com/test"
    assert evidence[0]["criterion"] == "affiliate_opportunities"
    assert evidence[0]["score"] == 6
    assert evidence[0]["is_demo"] is False


def test_approve_resets_niche_score(client):
    niche_id = make_niche(client)
    for criterion in CRITERIA:
        r = client.post(
            f"/api/v1/niches/{niche_id}/evidence",
            json={
                "criterion": criterion,
                "score": 7,
                "observation": "Demo observation for testing.",
                "is_demo": True,
            },
        )
        assert r.status_code == 201
    r = client.post(f"/api/v1/niches/{niche_id}/evaluate")
    assert r.json()["status"] == "evaluated"
    niche = client.get(f"/api/v1/niches/{niche_id}").json()["niche"]
    assert niche["latest_score"] is not None

    cand = create_candidate(client, niche_id)
    client.post(f"/api/v1/candidates/{cand['id']}/approve", json={})

    niche = client.get(f"/api/v1/niches/{niche_id}").json()["niche"]
    assert niche["score_status"] == "incomplete"
    assert niche["latest_score"] is None


def test_reject_creates_no_evidence(client):
    niche_id = make_niche(client)
    cand = create_candidate(client, niche_id)
    r = client.post(
        f"/api/v1/candidates/{cand['id']}/reject",
        json={"reviewer_note": "Source does not support the claim."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "rejected"
    assert body["evidence_id"] is None
    assert evidence_for(client, niche_id) == []


def test_reject_requires_a_note(client):
    niche_id = make_niche(client)
    cand = create_candidate(client, niche_id)
    r = client.post(f"/api/v1/candidates/{cand['id']}/reject", json={"reviewer_note": ""})
    assert r.status_code == 422


def test_decisions_are_final(client):
    niche_id = make_niche(client)
    cand = create_candidate(client, niche_id)
    client.post(f"/api/v1/candidates/{cand['id']}/approve", json={})

    again = client.post(f"/api/v1/candidates/{cand['id']}/approve", json={})
    assert again.status_code == 409
    reject_after = client.post(
        f"/api/v1/candidates/{cand['id']}/reject",
        json={"reviewer_note": "Changed my mind."},
    )
    assert reject_after.status_code == 409
    assert len(evidence_for(client, niche_id)) == 1


def test_list_filters_by_status(client):
    niche_id = make_niche(client)
    first = create_candidate(client, niche_id)
    create_candidate(client, niche_id, criterion="audience_demand")
    client.post(f"/api/v1/candidates/{first['id']}/approve", json={})

    pending = client.get("/api/v1/candidates").json()
    approved = client.get("/api/v1/candidates?status=approved").json()
    assert len(pending) == 1
    assert len(approved) == 1
    assert approved[0]["id"] == first["id"]