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


def test_newest_evidence_wins():
    older = make_evidence("audience_demand", 3)
    older.observed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newer = make_evidence("audience_demand", 9)
    newer.observed_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    others = [make_evidence(key, 5) for key in WEIGHTS if key != "audience_demand"]

    result = evaluate_evidence([newer, older, *others])  # order must not matter
    assert result["breakdown"]["audience_demand"]["score"] == 9


def test_worked_example_from_the_learning_guide():
    scores = {
        "audience_demand": 6, "monetization_potential": 7, "affiliate_opportunities": 5,
        "competition_accessibility": 8, "production_feasibility": 9,
        "long_term_demand": 7, "creator_capability": 6,
    }
    result = evaluate_evidence([make_evidence(k, v) for k, v in scores.items()])
    assert result["weighted_score"] == 6.7
    assert result["interpretation"].startswith("Promising")


def test_interpretation_bands():
    def interpretation(score):
        return evaluate_evidence([make_evidence(k, score) for k in WEIGHTS])["interpretation"]

    assert interpretation(8).startswith("Strong")
    assert interpretation(7).startswith("Promising")
    assert interpretation(5).startswith("Mixed")
    assert interpretation(4).startswith("Weak")


def test_demo_evidence_is_flagged():
    evidence = [make_evidence(key, 8, is_demo=True) for key in WEIGHTS]
    result = evaluate_evidence(evidence)
    assert result["contains_demo_evidence"] is True
    assert "Demonstration-only" in result["interpretation"]
