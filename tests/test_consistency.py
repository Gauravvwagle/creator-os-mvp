from typing import get_args

from app.agents.research_planner import CRITERIA_GUIDE
from app.schemas import Criterion
from app.scoring import WEIGHTS


def test_all_criterion_lists_agree():
    """If you add or rename a criterion, every place that knows about it must change."""
    assert set(get_args(Criterion)) == set(WEIGHTS)
    assert set(CRITERIA_GUIDE) == set(WEIGHTS)


def test_every_criterion_has_a_positive_weight():
    assert all(weight > 0 for weight in WEIGHTS.values())
