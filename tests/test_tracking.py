import json
from datetime import datetime, timedelta, timezone

import pytest

from app.api import content_routes

TODAY = datetime.now(timezone.utc).date()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)
SCRIPT_BODY = "Welcome back. Today we look at how affiliate programs work. " * 6


def make_niche(client, name="Tracked niche"):
    return client.post("/api/v1/niches", json={"name": name}).json()["id"]


def human_script(client, niche_id, body=SCRIPT_BODY):
    idea = client.post(f"/api/v1/niches/{niche_id}/content/ideas", json={"title": "A human idea", "hook": "Hook."}).json()
    script = client.post(f"/api/v1/content/ideas/{idea['id']}/scripts", json={"body": body}).json()
    return idea["id"], script["id"]


def make_post(client, niche_id, **overrides):
    body = {"platform": "youtube", "title": "My first video", "description": "About affiliates.", "tags": ["python", " learn "]}
    body.update(overrides)
    r = client.post(f"/api/v1/niches/{niche_id}/posts", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def published_post(client, niche_id, title="Published video", on=None):
    post = make_post(client, niche_id, title=title)
    assert client.post(f"/api/v1/posts/{post['id']}/approve").status_code == 200
    body = {"url": "https://www.youtube.com/watch?v=abc123"}
    if on:
        body["published_on"] = str(on)
    r = client.post(f"/api/v1/posts/{post['id']}/published", json=body)
    assert r.status_code == 200, r.text
    return post["id"]


# ---------- queue ----------

def test_post_lifecycle_planned_ready_published(client):
    niche_id = make_niche(client)
    post = make_post(client, niche_id)
    assert post["status"] == "planned" and post["tags"] == ["python", "learn"]

    assert client.post(f"/api/v1/posts/{post['id']}/published", json={"url": "https://example.com/v"}).status_code == 409
    assert client.get(f"/api/v1/posts/{post['id']}/package").status_code == 409

    ready = client.post(f"/api/v1/posts/{post['id']}/approve").json()
    assert ready["status"] == "ready" and ready["approved_at"] is not None
    assert client.post(f"/api/v1/posts/{post['id']}/approve").status_code == 409

    done = client.post(f"/api/v1/posts/{post['id']}/published", json={"url": "https://example.com/v"}).json()
    assert done["status"] == "published" and done["url"] == "https://example.com/v"
    assert done["published_on"] == str(TODAY)
    assert client.post(f"/api/v1/posts/{post['id']}/cancel").status_code == 409


def test_cancel_and_filters(client):
    niche_id = make_niche(client)
    a, b = make_post(client, niche_id, title="First"), make_post(client, niche_id, title="Second")
    assert client.post(f"/api/v1/posts/{a['id']}/cancel").json()["status"] == "cancelled"
    assert [p["title"] for p in client.get("/api/v1/posts?status=planned").json()] == ["Second"]
    assert len(client.get(f"/api/v1/posts?niche_id={niche_id}").json()) == 2
    assert client.post("/api/v1/posts/999/approve").status_code == 404


def test_future_publish_date_is_refused(client):
    niche_id = make_niche(client)
    post = make_post(client, niche_id)
    client.post(f"/api/v1/posts/{post['id']}/approve")
    r = client.post(f"/api/v1/posts/{post['id']}/published", json={"url": "https://example.com/v", "published_on": str(TOMORROW)})
    assert r.status_code == 422


def test_post_from_script_infers_the_idea(client):
    niche_id = make_niche(client)
    idea_id, script_id = human_script(client, niche_id)
    post = make_post(client, niche_id, script_id=script_id)
    assert post["idea_id"] == idea_id and post["script_id"] == script_id


def test_post_rejects_wrong_or_unapproved_links(client, monkeypatch):
    niche_id, other = make_niche(client), make_niche(client, "Other niche")
    idea_id, script_id = human_script(client, niche_id)
    other_idea, _ = human_script(client, other)

    def bad(**kw):
        return client.post(f"/api/v1/niches/{niche_id}/posts", json={"platform": "youtube", "title": "Some title", **kw})

    assert bad(idea_id=other_idea).status_code == 422          # idea from another niche
    assert bad(script_id=script_id, idea_id=other_idea).status_code == 422  # script and idea disagree
    assert bad(idea_id=9999).status_code == 404 and bad(script_id=9999).status_code == 404

    # An AI-drafted (unapproved) idea cannot be queued.
    client.post("/api/v1/niches/%d/candidates" % niche_id, json={
        "criterion": "audience_demand", "proposed_score": 6, "claim": "A real enough claim here.",
        "source_url": "https://example.com/s", "source_excerpt": "An excerpt long enough."})
    client.post("/api/v1/candidates/1/approve", json={})

    async def fake(prompt, json_mode=False):
        return json.dumps({"ideas": [{"title": "Draft idea title", "hook": "A hook sentence here.", "outline": ["one point", "two point"]}]})
    monkeypatch.setattr(content_routes, "generate_response", fake)
    draft_id = client.post(f"/api/v1/niches/{niche_id}/content/ideas/generate", json={"count": 1}).json()["ideas"][0]["id"]
    assert bad(idea_id=draft_id).status_code == 409


def test_package_has_everything_and_reminders(client):
    niche_id = make_niche(client)
    _, script_id = human_script(client, niche_id)
    post = make_post(client, niche_id, script_id=script_id)
    client.post(f"/api/v1/posts/{post['id']}/approve")
    package = client.get(f"/api/v1/posts/{post['id']}/package").json()
    assert "My first video" in package["text"] and "python, learn" in package["text"]
    assert "Welcome back." in package["text"]
    assert any("does not post for you" in r for r in package["reminders"])
    assert any("sponsored content" in r for r in package["reminders"])


# ---------- performance ----------

def test_performance_only_for_published_posts(client):
    niche_id = make_niche(client)
    post = make_post(client, niche_id)
    assert client.post(f"/api/v1/posts/{post['id']}/performance", json={"views": 10}).status_code == 409


def test_performance_is_recorded_replaced_per_day_and_listed_in_order(client):
    niche_id = make_niche(client)
    post_id = published_post(client, niche_id, on=YESTERDAY)
    url = f"/api/v1/posts/{post_id}/performance"
    client.post(url, json={"captured_on": str(TODAY), "views": 200, "likes": 20})
    client.post(url, json={"captured_on": str(YESTERDAY), "views": 100, "likes": 5})
    again = client.post(url, json={"captured_on": str(TODAY), "views": 250, "likes": 30, "comments": 4}).json()
    assert again["views"] == 250
    rows = client.get(url).json()
    assert [r["captured_on"] for r in rows] == [str(YESTERDAY), str(TODAY)]  # one row per day, oldest first
    assert rows[1]["views"] == 250


@pytest.mark.parametrize(
    "body",
    [{"views": -1}, {"views": 5, "likes": -2}, {"views": 5, "watch_time_minutes": -1}, {"captured_on": str(TOMORROW), "views": 5}],
)
def test_performance_validation(client, body):
    post_id = published_post(client, make_niche(client), on=YESTERDAY)
    assert client.post(f"/api/v1/posts/{post_id}/performance", json=body).status_code == 422


def test_performance_cannot_predate_publishing(client):
    post_id = published_post(client, make_niche(client), on=TODAY)
    r = client.post(f"/api/v1/posts/{post_id}/performance", json={"captured_on": str(YESTERDAY), "views": 5})
    assert r.status_code == 422 and client.post("/api/v1/posts/999/performance", json={"views": 1}).status_code == 404


# ---------- money ----------

def money(client, niche_id, **overrides):
    body = {"kind": "revenue", "source": "adsense", "amount": "12.34", "currency": "usd"}
    body.update(overrides)
    return client.post(f"/api/v1/niches/{niche_id}/money", json=body)


def test_money_is_stored_in_whole_cents_with_uppercase_currency(client):
    niche_id = make_niche(client)
    r = money(client, niche_id)
    assert r.status_code == 201
    assert r.json()["amount_cents"] == 1234 and r.json()["amount"] == "12.34" and r.json()["currency"] == "USD"
    assert money(client, niche_id, amount="0.10").json()["amount_cents"] == 10  # no float rounding surprises


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": "0"}, {"amount": "-5"}, {"amount": "1.234"}, {"currency": "US"}, {"currency": "US1"},
        {"kind": "revenue", "source": "tool"}, {"kind": "cost", "source": "adsense"}, {"occurred_on": str(TOMORROW)},
    ],
)
def test_money_validation(client, overrides):
    assert money(client, make_niche(client), **overrides).status_code == 422


def test_money_can_link_only_to_a_published_post_in_the_same_niche(client):
    niche_id, other = make_niche(client), make_niche(client, "Other")
    planned = make_post(client, niche_id)
    assert money(client, niche_id, post_id=planned["id"]).status_code == 409
    assert money(client, niche_id, post_id=9999).status_code == 404
    live = published_post(client, other)
    assert money(client, niche_id, post_id=live).status_code == 422
    assert money(client, make_niche(client, "Third"), post_id=live).status_code == 422
    assert money(client, other, post_id=live).status_code == 201
    assert money(client, 9999).status_code == 404


def test_money_list_and_delete(client):
    niche_id = make_niche(client)
    keep, drop = money(client, niche_id).json(), money(client, niche_id, amount="5").json()
    assert client.delete(f"/api/v1/money/{drop['id']}").status_code == 204
    assert [e["id"] for e in client.get(f"/api/v1/niches/{niche_id}/money").json()] == [keep["id"]]
    assert client.delete(f"/api/v1/money/{drop['id']}").status_code == 404


# ---------- outcomes report ----------

def outcome(client, niche_id):
    rows = client.get("/api/v1/reports/outcomes").json()["niches"]
    return next(r for r in rows if r["niche_id"] == niche_id)


def test_outcomes_use_the_latest_cumulative_snapshot_not_a_sum(client):
    niche_id = make_niche(client)
    post_id = published_post(client, niche_id, on=YESTERDAY)
    client.post(f"/api/v1/posts/{post_id}/performance", json={"captured_on": str(YESTERDAY), "views": 100, "likes": 10})
    client.post(f"/api/v1/posts/{post_id}/performance", json={"captured_on": str(TODAY), "views": 150, "likes": 12, "comments": 3, "followers_gained": 4})
    row = outcome(client, niche_id)
    assert row["total_views"] == 150          # not 250
    assert row["avg_views_per_measured_post"] == 150
    assert row["engagement_rate"] == 0.1      # (12 + 3) / 150
    assert row["followers_gained"] == 4 and row["posts_published"] == 1


def test_outcomes_keep_currencies_separate(client):
    niche_id = make_niche(client)
    money(client, niche_id, amount="100", currency="USD")
    money(client, niche_id, kind="cost", source="tool", amount="30.50", currency="USD")
    money(client, niche_id, amount="5000", currency="NPR", source="affiliate")
    assert outcome(client, niche_id)["money"] == {
        "NPR": {"revenue": "5000.00", "cost": "0.00", "net": "5000.00"},
        "USD": {"revenue": "100.00", "cost": "30.50", "net": "69.50"},
    }


def test_negative_net_is_shown(client):
    niche_id = make_niche(client)
    money(client, niche_id, kind="cost", source="ads_spend", amount="20")
    assert outcome(client, niche_id)["money"]["USD"]["net"] == "-20.00"


def test_outcomes_refuse_conclusions_from_few_posts(client):
    niche_id = make_niche(client)
    for i in range(4):
        published_post(client, niche_id, title=f"Video {i}")
    row = outcome(client, niche_id)
    assert row["enough_data"] is False and "too few" in row["data_note"]
    published_post(client, niche_id, title="Video 5")
    row = outcome(client, niche_id)
    assert row["enough_data"] is True and row["posts_published"] == 5


def test_unpublished_posts_and_empty_niches_are_handled(client):
    niche_id = make_niche(client)
    make_post(client, niche_id)  # planned, not published
    row = outcome(client, niche_id)
    assert row["posts_published"] == 0 and row["total_views"] == 0
    assert row["avg_views_per_measured_post"] is None and row["engagement_rate"] is None
    assert row["research_status"] == "incomplete" and row["research_score"] is None and row["money"] == {}


def test_published_post_without_performance_is_counted_but_not_averaged(client):
    niche_id = make_niche(client)
    published_post(client, niche_id)
    row = outcome(client, niche_id)
    assert row["posts_published"] == 1 and row["posts_with_performance"] == 0
    assert row["avg_views_per_measured_post"] is None
