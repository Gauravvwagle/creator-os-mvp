from app.scoring import WEIGHTS


def make_niche(client, name):
    r = client.post("/api/v1/niches", json={"name": name})
    assert r.status_code == 201
    return r.json()["id"]


def add_one(client, niche_id, criterion, score, is_demo):
    if is_demo:
        r = client.post(
            f"/api/v1/niches/{niche_id}/evidence",
            json={"criterion": criterion, "score": score,
                  "observation": "Test observation with enough detail.", "is_demo": True},
        )
        assert r.status_code == 201
        return
    # Real evidence: propose a candidate, then approve it (the only road to real evidence).
    r = client.post(
        f"/api/v1/niches/{niche_id}/candidates",
        json={"criterion": criterion, "proposed_score": score,
              "claim": "TEST ONLY: placeholder claim for testing.",
              "source_url": "https://example.com/source",
              "source_excerpt": "TEST ONLY: placeholder excerpt for testing."},
    )
    assert r.status_code == 201, r.text
    assert client.post(f"/api/v1/candidates/{r.json()['id']}/approve", json={}).status_code == 200


def add_all_criteria(client, niche_id, score, is_demo):
    for criterion in WEIGHTS:
        add_one(client, niche_id, criterion, score, is_demo)


def test_demo_niche_never_outranks_real_niche(client):
    demo_id = make_niche(client, "Demo niche")
    real_id = make_niche(client, "Real niche")
    add_all_criteria(client, demo_id, score=9, is_demo=True)
    add_all_criteria(client, real_id, score=6, is_demo=False)

    ranked = client.get("/api/v1/reports/rankings").json()["ranked"]
    assert [row["niche_name"] for row in ranked] == ["Real niche", "Demo niche"]
    assert ranked[0]["weighted_score"] == 6.0
    assert ranked[1]["contains_demo_evidence"] is True


def test_real_niches_are_sorted_best_first(client):
    low = make_niche(client, "Low")
    high = make_niche(client, "High")
    add_all_criteria(client, low, score=5, is_demo=False)
    add_all_criteria(client, high, score=8, is_demo=False)

    ranked = client.get("/api/v1/reports/rankings").json()["ranked"]
    assert [row["niche_name"] for row in ranked] == ["High", "Low"]


def test_incomplete_niche_is_listed_separately(client):
    complete = make_niche(client, "Complete")
    partial = make_niche(client, "Partial")
    add_all_criteria(client, complete, score=7, is_demo=False)
    add_one(client, partial, "audience_demand", 7, is_demo=False)

    body = client.get("/api/v1/reports/rankings").json()
    assert [row["niche_name"] for row in body["ranked"]] == ["Complete"]
    assert [row["niche_name"] for row in body["incomplete"]] == ["Partial"]


def test_adding_evidence_resets_a_stored_score(client):
    niche_id = make_niche(client, "Resettable")
    add_all_criteria(client, niche_id, score=7, is_demo=False)
    assert client.post(f"/api/v1/niches/{niche_id}/evaluate").json()["status"] == "evaluated"

    add_one(client, niche_id, "audience_demand", 9, is_demo=True)
    niche = client.get(f"/api/v1/niches/{niche_id}").json()["niche"]
    assert niche["score_status"] == "incomplete"
    assert niche["latest_score"] is None


def test_duplicate_niche_name_returns_409(client):
    make_niche(client, "Same name")
    r = client.post("/api/v1/niches", json={"name": "Same name"})
    assert r.status_code == 409


def test_unknown_niche_returns_404(client):
    assert client.get("/api/v1/niches/9999").status_code == 404
    assert client.post("/api/v1/niches/9999/evaluate").status_code == 404


def test_direct_entry_rejects_real_evidence(client):
    niche_id = make_niche(client, "Gate niche")
    r = client.post(
        f"/api/v1/niches/{niche_id}/evidence",
        json={"criterion": "audience_demand", "score": 8,
              "observation": "Unsourced real evidence should be refused."},
    )
    assert r.status_code == 403
    assert "candidates" in r.json()["detail"]
    assert client.get(f"/api/v1/niches/{niche_id}").json()["evidence"] == []


def test_direct_entry_still_accepts_demo_evidence(client):
    niche_id = make_niche(client, "Demo entry niche")
    r = client.post(
        f"/api/v1/niches/{niche_id}/evidence",
        json={"criterion": "audience_demand", "score": 8, "is_demo": True,
              "observation": "Demonstration data is allowed through direct entry."},
    )
    assert r.status_code == 201
