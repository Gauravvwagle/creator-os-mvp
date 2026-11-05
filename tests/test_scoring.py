from datetime import datetime, timezone
from types import SimpleNamespace
from app.scoring import WEIGHTS, evaluate_evidence


def make_evidence(criterion, score=8, is_demo=False):
    return SimpleNamespace(
        criterion=criterion,
        score=score,
        confidence="medium",
        observation="Test observation with enough detail.",
        source_url="https://example.com",
        is_demo=is_demo,
        observed_at=datetime.now(timezone.utc),
    )


def test_weights_total_100():
    assert sum(WEIGHTS.values()) == 100


def test_incomplete_evidence_is_not_scored():
    result = evaluate_evidence([make_evidence("audience_demand")])
    assert result["status"] == "incomplete"
    assert result["weighted_score"] is None
    assert len(result["criteria_missing"]) == 6


def test_all_equal_scores_return_same_score():
    evidence = [make_evidence(key, 7) for key in WEIGHTS]
    result = evaluate_evidence(evidence)
    assert result["status"] == "evaluated"
    assert result["weighted_score"] == 7.0


def test_demo_evidence_is_flagged():
    evidence = [make_evidence(key, 8, is_demo=True) for key in WEIGHTS]
    result = evaluate_evidence(evidence)
    assert result["contains_demo_evidence"] is True
    assert "Demonstration-only" in result["interpretation"]
