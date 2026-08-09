from __future__ import annotations

import pytest

from app.agents.scoring import QueryCandidate, VisibilityScoringAgent
from app.services.external_data import SearchMetrics, VisibilityResult
from app.utils.errors import ExternalDataError
from app.utils.scoring import calculate_opportunity_score


class FakeExternal:
    def __init__(self, visible=False, fail_query=None):
        self.visible = visible
        self.fail_query = fail_query

    def get_keyword_metrics(self, queries):
        return {query: SearchMetrics(1200, 62) for query in queries}

    def check_ai_visibility(self, query, _domain):
        if query == self.fail_query:
            raise ExternalDataError("timeout")
        return VisibilityResult(self.visible, 2 if self.visible else None, tokens_used=5)


def test_scoring_agent_success_and_visibility_false():
    result = VisibilityScoringAgent(FakeExternal()).run(
        "best seo content tool", "example.com", "commercial"
    )
    assert result.domain_visible is False
    assert result.visibility_position is None
    assert result.opportunity_score > 0.7


def test_scoring_agent_visibility_true_lowers_score():
    hidden = VisibilityScoringAgent(FakeExternal(False)).run(
        "best seo content tool", "example.com", "commercial"
    )
    visible = VisibilityScoringAgent(FakeExternal(True)).run(
        "best seo content tool", "example.com", "commercial"
    )
    assert visible.visibility_position == 2
    assert hidden.opportunity_score > visible.opportunity_score


def test_scoring_batch_continues_after_external_failure():
    candidates = [
        QueryCandidate(query_text="works", intent="commercial"),
        QueryCandidate(query_text="fails", intent="comparison"),
    ]
    batch = VisibilityScoringAgent(FakeExternal(fail_query="fails")).run_batch(
        candidates, "example.com"
    )
    assert set(batch.successes) == {"works"}
    assert set(batch.failures) == {"fails"}


def test_high_value_gap_scores_higher_than_low_visible_query():
    high = calculate_opportunity_score(5000, 10, False, "commercial", 5000)
    low = calculate_opportunity_score(10, 95, True, "informational", 5000)
    assert high > 0.85
    assert low < 0.3


def test_visibility_gap_affects_equivalent_query():
    hidden = calculate_opportunity_score(1000, 50, False, "commercial", 1000)
    visible = calculate_opportunity_score(1000, 50, True, "commercial", 1000)
    assert hidden - visible == pytest.approx(0.25)


@pytest.mark.parametrize(
    "args", [(-10, -5, False, "commercial", -1), (10**12, 999, True, "unknown", 1)]
)
def test_score_is_always_clamped(args):
    score = calculate_opportunity_score(*args)
    assert 0.0 <= score <= 1.0
