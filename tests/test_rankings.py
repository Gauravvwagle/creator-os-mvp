from app.scoring import WEIGHTS


def make_niche(client, name):
    r = client.post("/api/v1/niches", json={"name": name})
    assert r.status_code == 201
    return r.json()["id"]


def add_all_criteria(client, niche_id, score, is_demo):
    for criterion in WEIGHTS:
        r = client.post(
            f"/api/v1/niches/{niche_id}/evidence",
            json={
                "criterion": criterion,
                "score": score,
                "observation": "Test observation with enough detail.",
                "is_demo": is_demo,
            },
        )
        assert r.status_code == 201


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
    client.post(
        f"/api/v1/niches/{partial}/evidence",
        json={"criterion": "audience_demand", "score": 7,
              "observation": "Only one criterion recorded."},
    )

    body = client.get("/api/v1/reports/rankings").json()
    assert [row["niche_name"] for row in body["ranked"]] == ["Complete"]
    assert [row["niche_name"] for row in body["incomplete"]] == ["Partial"]


def test_adding_evidence_resets_a_stored_score(client):
    niche_id = make_niche(client, "Resettable")
    add_all_criteria(client, niche_id, score=7, is_demo=False)
    assert client.post(f"/api/v1/niches/{niche_id}/evaluate").json()["status"] == "evaluated"

    client.post(
        f"/api/v1/niches/{niche_id}/evidence",
        json={"criterion": "audience_demand", "score": 9,
              "observation": "A newer observation arrives."},
    )
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
