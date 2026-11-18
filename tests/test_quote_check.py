import pytest

from app.api import candidate_routes
from app.research.fetcher import FetchError

EXCERPT = "Members earn a 30% commission on every qualifying sale."


def make_niche(client, name="Quote niche"):
    r = client.post("/api/v1/niches", json={"name": name})
    assert r.status_code == 201
    return r.json()["id"]


def make_candidate(client, niche_id, excerpt=EXCERPT):
    r = client.post(
        f"/api/v1/niches/{niche_id}/candidates",
        json={
            "criterion": "affiliate_opportunities",
            "proposed_score": 6,
            "claim": "TEST ONLY: placeholder claim for testing.",
            "source_url": "https://example.com/program",
            "source_excerpt": excerpt,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def fake_page(text):
    async def fetch(url):
        return {"final_url": url, "title": "Test page", "text": text}
    return fetch


def failing_fetch():
    async def fetch(url):
        raise FetchError("The page took too long to respond.")
    return fetch


def evidence_text(client, niche_id):
    return client.get(f"/api/v1/niches/{niche_id}").json()["evidence"][0]["observation"]


def test_new_candidate_is_not_checked(client):
    cand = make_candidate(client, make_niche(client))
    assert cand["quote_check_status"] == "not_checked"
    assert cand["quote_checked_at"] is None


def test_verify_records_found(client, monkeypatch):
    monkeypatch.setattr(candidate_routes, "fetch_page_text", fake_page(f"Intro. {EXCERPT} Footer."))
    cand = make_candidate(client, make_niche(client))
    r = client.post(f"/api/v1/candidates/{cand['id']}/verify")
    assert r.status_code == 200
    body = r.json()
    assert body["quote_check_status"] == "found"
    assert body["quote_checked_at"] is not None
    assert body["status"] == "pending"  # checking never decides anything


def test_verify_records_not_found(client, monkeypatch):
    monkeypatch.setattr(candidate_routes, "fetch_page_text", fake_page("A page with different words."))
    cand = make_candidate(client, make_niche(client))
    body = client.post(f"/api/v1/candidates/{cand['id']}/verify").json()
    assert body["quote_check_status"] == "not_found"


def test_verify_records_fetch_failure_instead_of_erroring(client, monkeypatch):
    monkeypatch.setattr(candidate_routes, "fetch_page_text", failing_fetch())
    cand = make_candidate(client, make_niche(client))
    r = client.post(f"/api/v1/candidates/{cand['id']}/verify")
    assert r.status_code == 200
    assert r.json()["quote_check_status"] == "fetch_failed"


def test_verify_unknown_candidate_returns_404(client):
    assert client.post("/api/v1/candidates/9999/verify").status_code == 404


def test_cannot_verify_after_a_decision(client, monkeypatch):
    monkeypatch.setattr(candidate_routes, "fetch_page_text", fake_page(EXCERPT))
    cand = make_candidate(client, make_niche(client))
    client.post(f"/api/v1/candidates/{cand['id']}/approve", json={})
    assert client.post(f"/api/v1/candidates/{cand['id']}/verify").status_code == 409


def test_second_check_overwrites_the_first(client, monkeypatch):
    cand = make_candidate(client, make_niche(client))
    monkeypatch.setattr(candidate_routes, "fetch_page_text", fake_page("nothing relevant"))
    assert client.post(f"/api/v1/candidates/{cand['id']}/verify").json()["quote_check_status"] == "not_found"
    monkeypatch.setattr(candidate_routes, "fetch_page_text", fake_page(EXCERPT))
    assert client.post(f"/api/v1/candidates/{cand['id']}/verify").json()["quote_check_status"] == "found"


@pytest.mark.parametrize(
    "page_text, expected",
    [
        (EXCERPT, "was found in the page text"),
        ("something else entirely", "WARNING - the excerpt was NOT found"),
    ],
)
def test_approved_evidence_records_the_check(client, monkeypatch, page_text, expected):
    monkeypatch.setattr(candidate_routes, "fetch_page_text", fake_page(page_text))
    niche_id = make_niche(client)
    cand = make_candidate(client, niche_id)
    client.post(f"/api/v1/candidates/{cand['id']}/verify")
    assert client.post(f"/api/v1/candidates/{cand['id']}/approve", json={}).status_code == 200
    assert expected in evidence_text(client, niche_id)


def test_failed_check_warns_but_does_not_block_approval(client, monkeypatch):
    monkeypatch.setattr(candidate_routes, "fetch_page_text", failing_fetch())
    niche_id = make_niche(client)
    cand = make_candidate(client, niche_id)
    client.post(f"/api/v1/candidates/{cand['id']}/verify")
    r = client.post(f"/api/v1/candidates/{cand['id']}/approve", json={})
    assert r.status_code == 200
    assert "could not be fetched" in evidence_text(client, niche_id)


def test_approving_an_unchecked_candidate_says_so(client):
    niche_id = make_niche(client)
    cand = make_candidate(client, niche_id)
    client.post(f"/api/v1/candidates/{cand['id']}/approve", json={})
    assert "NOT machine-checked" in evidence_text(client, niche_id)
