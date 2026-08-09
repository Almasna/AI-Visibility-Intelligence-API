from __future__ import annotations

import pytest

from app.agents.scoring import ScoringBatchResult, VisibilityScoringResult
from app.extensions import db
from app.models import ContentRecommendation, DiscoveredQuery, PipelineRun
from app.schemas.agents import DiscoveredQueryResult, RecommendationResult
from app.services.pipeline import PipelineService
from app.utils.errors import AgentError, ApiError


class FakeDiscovery:
    last_tokens_used = 10

    def __init__(self, fail=False):
        self.fail = fail

    def run(self, _profile):
        if self.fail:
            raise AgentError("bad discovery")
        return [
            DiscoveredQueryResult(
                query_text=f"Commercial SEO software question {index}?",
                intent="commercial" if index != 2 else "comparison",
            )
            for index in range(3)
        ]


class FakeScoring:
    def __init__(self, fail_index=None):
        self.fail_index = fail_index

    def run_batch(self, candidates, _domain):
        successes = {}
        failures = {}
        for index, candidate in enumerate(candidates):
            if index == self.fail_index:
                failures[candidate.query_text] = "provider timeout"
                continue
            successes[candidate.query_text] = VisibilityScoringResult(
                query_text=candidate.query_text,
                search_intent=candidate.intent,
                estimated_search_volume=1000 - index * 100,
                competitive_difficulty=40 + index,
                domain_visible=False,
                visibility_position=None,
                visibility_source="test-provider",
                opportunity_score=0.9 - index * 0.1,
                tokens_used=5,
            )
        return ScoringBatchResult(successes, failures)


class FakeRecommendation:
    last_tokens_used = 20

    def __init__(self, fail=False):
        self.fail = fail

    def run(self, _profile, gaps):
        if self.fail:
            raise AgentError("bad recommendations")
        return [
            RecommendationResult(
                target_query_text=gaps[index % len(gaps)].query_text,
                content_type=["blog_post", "comparison_page", "guide"][index],
                title=f"Specific content recommendation title {index}",
                rationale="This recommendation directly closes the measured content gap.",
                target_keywords=["seo software", f"optimization {index}"],
                priority="high" if index == 0 else "medium",
            )
            for index in range(3)
        ]


def test_complete_pipeline_persists_all_stages(app, profile):
    result = PipelineService(
        FakeDiscovery(), FakeScoring(), FakeRecommendation()
    ).run(profile)
    assert result["status"] == "completed"
    assert result["queries_discovered"] == 3
    assert result["queries_scored"] == 3
    assert result["tokens_used"] == 45
    assert db.session.scalar(db.select(db.func.count(DiscoveredQuery.uuid))) == 3
    assert db.session.scalar(db.select(db.func.count(ContentRecommendation.uuid))) == 3


def test_one_agent_two_failure_does_not_stop_pipeline(app, profile):
    result = PipelineService(
        FakeDiscovery(), FakeScoring(fail_index=1), FakeRecommendation()
    ).run(profile)
    assert result["status"] == "partially_completed"
    assert result["queries_scored"] == 2
    failed = db.session.scalar(
        db.select(DiscoveredQuery).where(DiscoveredQuery.scoring_error.is_not(None))
    )
    assert failed.scoring_error == "provider timeout"
    assert db.session.scalar(db.select(db.func.count(ContentRecommendation.uuid))) == 3


def test_agent_one_failure_marks_run_failed(app, profile):
    with pytest.raises(ApiError) as raised:
        PipelineService(
            FakeDiscovery(fail=True), FakeScoring(), FakeRecommendation()
        ).run(profile)
    assert raised.value.code == "PIPELINE_FAILED"
    run = db.session.scalar(db.select(PipelineRun))
    assert run.status == "failed"
    assert run.queries_discovered == 0


def test_agent_three_failure_preserves_queries_and_scores(app, profile):
    result = PipelineService(
        FakeDiscovery(), FakeScoring(), FakeRecommendation(fail=True)
    ).run(profile)
    assert result["status"] == "partially_completed"
    assert result["recommendations"] == []
    assert db.session.scalar(db.select(db.func.count(DiscoveredQuery.uuid))) == 3
    run = db.session.get(PipelineRun, result["pipeline_run_uuid"])
    assert "Content recommendation failed" in run.error_message
