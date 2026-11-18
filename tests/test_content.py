import json

import httpx
import pytest

from app.api import content_routes
from app.content.planning import (
    PlanningError,
    clean_script,
    find_unsupported_numbers,
    parse_ideas,
)

IDEA = {
    "title": "How affiliate programs really work",
    "hook": "Most beginners never read the terms before they join.",
    "outline": ["What an affiliate program is", "Where to find the terms", "What to check before joining"],
}
IDEAS_JSON = {"ideas": [IDEA, {**IDEA, "title": "Reading commission tables"}]}
SCRIPT = ("Welcome back. Today we look at how affiliate programs work. " * 8).strip()


def fake_model(*answers):
    queue = list(answers)

    async def generate(prompt, json_mode=False):
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item if isinstance(item, str) else json.dumps(item)
    return generate


def make_niche(client, name="Affiliate basics"):
    return client.post("/api/v1/niches", json={"name": name}).json()["id"]


def add_real_evidence(client, niche_id, claim="The programme pays a 30% commission on annual plans."):
    """Real evidence can only arrive through the candidate gate."""
    r = client.post(
        f"/api/v1/niches/{niche_id}/candidates",
        json={"criterion": "affiliate_opportunities", "proposed_score": 7, "claim": claim,
              "source_url": "https://example.com/terms",
              "source_excerpt": "Partners earn 30% on every annual plan they refer."},
    )
    assert client.post(f"/api/v1/candidates/{r.json()['id']}/approve", json={}).status_code == 200


def add_demo_evidence(client, niche_id):
    r = client.post(
        f"/api/v1/niches/{niche_id}/evidence",
        json={"criterion": "audience_demand", "score": 9, "is_demo": True,
              "observation": "DEMO ONLY secret demo phrase zebra."},
    )
    assert r.status_code == 201


def generate_ideas(client, niche_id, count=2):
    return client.post(f"/api/v1/niches/{niche_id}/content/ideas/generate", json={"count": count})


def approved_idea(client, monkeypatch, niche_id):
    monkeypatch.setattr(content_routes, "generate_response", fake_model(IDEAS_JSON))
    idea_id = generate_ideas(client, niche_id).json()["ideas"][0]["id"]
    assert client.post(f"/api/v1/content/ideas/{idea_id}/approve").status_code == 200
    return idea_id


# ---------- pure helpers ----------

def test_parse_ideas_keeps_valid_ones_and_caps_the_count():
    raw = json.dumps({"ideas": [IDEA, IDEA, IDEA]})
    assert len(parse_ideas(raw, max_ideas=2)) == 2


@pytest.mark.parametrize(
    "raw",
    [
        "nope",
        "[]",
        '{"ideas": "x"}',
        '{"ideas": []}',
        '{"ideas": [{"title": "ok title", "hook": "short", "outline": ["a point", "b point"]}]}',
        '{"ideas": [{"title": "Fine title here", "hook": "A fine hook sentence.", "outline": ["only one"]}]}',
        '{"ideas": [{"title": "Fine title here", "hook": "A fine hook sentence.", "outline": ["ok one", 5]}]}',
    ],
)
def test_parse_ideas_rejects_unusable_answers(raw):
    with pytest.raises(PlanningError):
        parse_ideas(raw, max_ideas=3)


def test_one_bad_idea_does_not_spoil_the_good_one():
    raw = json.dumps({"ideas": [{"title": "x"}, IDEA]})
    assert [i["title"] for i in parse_ideas(raw, 3)] == [IDEA["title"]]


def test_clean_script_enforces_length():
    with pytest.raises(PlanningError):
        clean_script("too short")
    with pytest.raises(PlanningError):
        clean_script("x" * 9000)
    assert clean_script("  " + SCRIPT + "  ") == SCRIPT


def test_unsupported_numbers_are_found():
    allowed = "The plan pays 30% commission. Terms updated in 2026."
    script = "It pays 30% and has 12,000 users. Tip 3 helps. Rated 4.5 stars in 2026. Up 47%."
    assert find_unsupported_numbers(script, allowed) == ["12000", "4.5", "47%"]


# ---------- ideas ----------

def test_ideas_need_real_approved_evidence(client, monkeypatch):
    monkeypatch.setattr(content_routes, "generate_response", fake_model(IDEAS_JSON))
    niche_id = make_niche(client)
    assert generate_ideas(client, niche_id).status_code == 409
    add_demo_evidence(client, niche_id)  # demo data does not count
    assert generate_ideas(client, niche_id).status_code == 409


def test_generated_ideas_are_drafts_and_use_only_real_evidence(client, monkeypatch):
    seen = {}

    async def spy(prompt, json_mode=False):
        seen["prompt"], seen["json_mode"] = prompt, json_mode
        return json.dumps(IDEAS_JSON)
    monkeypatch.setattr(content_routes, "generate_response", spy)
    niche_id = make_niche(client)
    add_real_evidence(client, niche_id)
    add_demo_evidence(client, niche_id)

    response = generate_ideas(client, niche_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["ideas"]) == 2 and "not evidence" in body["note"]
    assert all(i["status"] == "draft" and i["origin"] == "ai_draft" for i in body["ideas"])
    assert "30%" in seen["prompt"] and "Affiliate basics" in seen["prompt"]
    assert "zebra" not in seen["prompt"]  # demo evidence never reaches the model
    assert seen["json_mode"] is True


def test_unusable_model_output_saves_nothing(client, monkeypatch):
    monkeypatch.setattr(content_routes, "generate_response", fake_model("garbage"))
    niche_id = make_niche(client)
    add_real_evidence(client, niche_id)
    response = generate_ideas(client, niche_id)
    assert response.status_code == 502 and "Nothing was saved" in response.json()["detail"]
    assert client.get("/api/v1/content/ideas").json() == []


def test_second_attempt_can_recover(client, monkeypatch):
    monkeypatch.setattr(content_routes, "generate_response", fake_model("garbage", IDEAS_JSON))
    niche_id = make_niche(client)
    add_real_evidence(client, niche_id)
    assert generate_ideas(client, niche_id).status_code == 200


def test_ollama_errors_map_to_503_and_504(client, monkeypatch):
    niche_id = make_niche(client)
    add_real_evidence(client, niche_id)
    monkeypatch.setattr(content_routes, "generate_response", fake_model(RuntimeError("Cannot connect to Ollama.")))
    assert generate_ideas(client, niche_id).status_code == 503
    monkeypatch.setattr(content_routes, "generate_response", fake_model(httpx.ReadTimeout("slow")))
    assert generate_ideas(client, niche_id).status_code == 504


def test_idea_decisions_are_final_and_rejection_needs_a_note(client, monkeypatch):
    monkeypatch.setattr(content_routes, "generate_response", fake_model(IDEAS_JSON))
    niche_id = make_niche(client)
    add_real_evidence(client, niche_id)
    first, second = [i["id"] for i in generate_ideas(client, niche_id).json()["ideas"]]

    assert client.post(f"/api/v1/content/ideas/{first}/reject", json={}).status_code == 422
    assert client.post(f"/api/v1/content/ideas/{first}/reject", json={"reviewer_note": "Too generic."}).status_code == 200
    assert client.post(f"/api/v1/content/ideas/{first}/approve").status_code == 409
    assert client.post(f"/api/v1/content/ideas/{second}/approve").json()["status"] == "approved"
    assert client.post(f"/api/v1/content/ideas/{second}/reject", json={"reviewer_note": "Changed mind."}).status_code == 409
    assert client.post("/api/v1/content/ideas/999/approve").status_code == 404


def test_human_idea_starts_approved_and_list_filters_work(client):
    niche_id = make_niche(client)
    r = client.post(f"/api/v1/niches/{niche_id}/content/ideas", json={"title": "My own idea", "hook": "A hook."})
    assert r.status_code == 201
    assert r.json()["status"] == "approved" and r.json()["origin"] == "human_entered"
    assert len(client.get(f"/api/v1/content/ideas?niche_id={niche_id}&status=approved").json()) == 1
    assert client.get("/api/v1/content/ideas?status=draft").json() == []
    assert client.post("/api/v1/niches/999/content/ideas", json={"title": "No niche here"}).status_code == 404


# ---------- scripts ----------

def test_script_needs_an_approved_idea(client, monkeypatch):
    monkeypatch.setattr(content_routes, "generate_response", fake_model(IDEAS_JSON))
    niche_id = make_niche(client)
    add_real_evidence(client, niche_id)
    draft_id = generate_ideas(client, niche_id).json()["ideas"][0]["id"]
    assert client.post(f"/api/v1/content/ideas/{draft_id}/scripts/generate").status_code == 409
    assert client.post(f"/api/v1/content/ideas/{draft_id}/scripts", json={"body": "x" * 30}).status_code == 409


def test_generated_script_is_a_draft_and_flags_invented_numbers(client, monkeypatch):
    niche_id = make_niche(client)
    add_real_evidence(client, niche_id)
    idea_id = approved_idea(client, monkeypatch, niche_id)

    script_text = SCRIPT + " The programme pays 30% commission. Creators saw a 47% jump and 12,000 views."
    monkeypatch.setattr(content_routes, "generate_response", fake_model(script_text))
    response = client.post(f"/api/v1/content/ideas/{idea_id}/scripts/generate")
    assert response.status_code == 200, response.text
    script = response.json()
    assert script["status"] == "draft" and script["origin"] == "ai_draft"
    assert script["unverified_numbers"] == ["47%", "12000"]  # 30% is in the evidence, so it is not flagged


def test_script_prompt_contains_the_evidence_but_not_demo_data(client, monkeypatch):
    niche_id = make_niche(client)
    add_real_evidence(client, niche_id)
    add_demo_evidence(client, niche_id)
    idea_id = approved_idea(client, monkeypatch, niche_id)

    seen = {}

    async def spy(prompt, json_mode=False):
        seen["prompt"], seen["json_mode"] = prompt, json_mode
        return SCRIPT
    monkeypatch.setattr(content_routes, "generate_response", spy)
    client.post(f"/api/v1/content/ideas/{idea_id}/scripts/generate")
    assert "30%" in seen["prompt"] and "NEEDS SOURCE" in seen["prompt"]
    assert "zebra" not in seen["prompt"]
    assert seen["json_mode"] is False


def test_too_short_script_is_refused(client, monkeypatch):
    niche_id = make_niche(client)
    add_real_evidence(client, niche_id)
    idea_id = approved_idea(client, monkeypatch, niche_id)
    monkeypatch.setattr(content_routes, "generate_response", fake_model("Too short."))
    assert client.post(f"/api/v1/content/ideas/{idea_id}/scripts/generate").status_code == 502
    assert client.get("/api/v1/content/scripts").json() == []


def test_script_decisions_are_final(client, monkeypatch):
    niche_id = make_niche(client)
    add_real_evidence(client, niche_id)
    idea_id = approved_idea(client, monkeypatch, niche_id)
    monkeypatch.setattr(content_routes, "generate_response", fake_model(SCRIPT))
    script_id = client.post(f"/api/v1/content/ideas/{idea_id}/scripts/generate").json()["id"]

    assert client.post(f"/api/v1/content/scripts/{script_id}/approve").json()["status"] == "approved"
    assert client.post(f"/api/v1/content/scripts/{script_id}/reject", json={"reviewer_note": "Nope."}).status_code == 409
    assert client.post("/api/v1/content/scripts/999/approve").status_code == 404
    assert len(client.get(f"/api/v1/content/scripts?idea_id={idea_id}&status=approved").json()) == 1


def test_human_script_starts_approved(client, monkeypatch):
    niche_id = make_niche(client)
    add_real_evidence(client, niche_id)
    idea_id = approved_idea(client, monkeypatch, niche_id)
    r = client.post(f"/api/v1/content/ideas/{idea_id}/scripts", json={"body": "My own words for the video, written by me."})
    assert r.status_code == 201
    assert r.json()["status"] == "approved" and r.json()["origin"] == "human_entered"
