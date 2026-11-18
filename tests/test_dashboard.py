from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dashboard_routes import router as dashboard_router
from app.scoring import WEIGHTS

PAGE = Path(__file__).resolve().parent.parent / "app" / "static" / "dashboard.html"


def test_dashboard_page_is_served_as_html():
    app = FastAPI()
    app.include_router(dashboard_router)
    response = TestClient(app).get("/dashboard")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "CreatorOS" in response.text


def test_dashboard_never_builds_markup_from_text():
    """Everything shown comes from user-typed or fetched data, so it must be inserted as
    text. If you ever need innerHTML here, sanitise the value and update this test."""
    source = PAGE.read_text(encoding="utf-8")
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert forbidden not in source, forbidden


def test_dashboard_does_not_load_outside_resources():
    source = PAGE.read_text(encoding="utf-8")
    assert "<script src=" not in source
    assert "https://cdn" not in source


def test_criteria_endpoint_matches_scoring_weights(client):
    response = client.get("/api/v1/criteria")
    assert response.status_code == 200
    assert {row["name"]: row["weight"] for row in response.json()} == WEIGHTS
