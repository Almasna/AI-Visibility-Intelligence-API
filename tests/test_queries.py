from __future__ import annotations

import pytest

from app.agents.scoring import VisibilityScoringResult
from app.extensions import db
from app.models import ContentRecommendation, DiscoveredQuery, PipelineRun


@pytest.fixture()
def seeded_queries(app, profile):
    run = PipelineRun(profile_uuid=profile.uuid, status="completed")
    db.session.add(run)
    db.session.flush()
    rows = [
        DiscoveredQuery(
            profile_uuid=profile.uuid,
            run_uuid=run.uuid,
            query_text="Highest hidden query",
            search_intent="commercial",
            estimated_search_volume=1500,
            competitive_difficulty=30,
            opportunity_score=0.9,
            domain_visible=False,
        ),
        DiscoveredQuery(
            profile_uuid=profile.uuid,
            run_uuid=run.uuid,
            query_text="Visible query",
            search_intent="comparison",
            estimated_search_volume=1000,
            competitive_difficulty=50,
            opportunity_score=0.7,
            domain_visible=True,
            visibility_position=2,
        ),
        DiscoveredQuery(
            profile_uuid=profile.uuid,
            run_uuid=run.uuid,
            query_text="Lower hidden query",
            search_intent="informational",
            estimated_search_volume=100,
            competitive_difficulty=80,
            opportunity_score=0.2,
            domain_visible=False,
        ),
        DiscoveredQuery(
            profile_uuid=profile.uuid,
            run_uuid=run.uuid,
            query_text="Unknown query",
            search_intent="commercial",
            domain_visible=None,
            scoring_error="no data",
        ),
    ]
    db.session.add_all(rows)
    db.session.flush()
    db.session.add(
        ContentRecommendation(
            profile_uuid=profile.uuid,
            query_uuid=rows[0].uuid,
            content_type="blog_post",
            title="A specific recommendation",
            rationale="This addresses a measured gap with commercially useful content.",
            target_keywords=["seo", "content"],
            priority="high",
        )
    )
    db.session.commit()
    return rows


def test_default_query_sorting(client, profile, seeded_queries):
    response = client.get(f"/api/v1/profiles/{profile.uuid}/queries")
    assert response.status_code == 200
    assert [item["query_text"] for item in response.json["items"]] == [
        "Highest hidden query",
        "Visible query",
        "Lower hidden query",
        "Unknown query",
    ]


def test_min_score_filter(client, profile, seeded_queries):
    response = client.get(f"/api/v1/profiles/{profile.uuid}/queries?min_score=0.7")
    assert len(response.json["items"]) == 2


@pytest.mark.parametrize(
    ("status", "expected"),
    [("visible", 1), ("not_visible", 2), ("unknown", 1)],
)
def test_visibility_filters(client, profile, seeded_queries, status, expected):
    response = client.get(
        f"/api/v1/profiles/{profile.uuid}/queries?status={status}"
    )
    assert len(response.json["items"]) == expected


def test_query_pagination(client, profile, seeded_queries):
    response = client.get(
        f"/api/v1/profiles/{profile.uuid}/queries?page=2&per_page=2"
    )
    assert response.json["pagination"] == {
        "page": 2,
        "per_page": 2,
        "total_items": 4,
        "total_pages": 2,
    }
    assert len(response.json["items"]) == 2


def test_invalid_pagination_is_safe(client, profile, seeded_queries):
    response = client.get(f"/api/v1/profiles/{profile.uuid}/queries?page=0")
    assert response.status_code == 422
    assert response.json["error"]["code"] == "VALIDATION_ERROR"


def test_recommendations_endpoint(client, profile, seeded_queries):
    response = client.get(f"/api/v1/profiles/{profile.uuid}/recommendations")
    assert response.status_code == 200
    assert response.json["items"][0]["priority"] == "high"


def test_recheck_updates_existing_query_only(app, client, profile, seeded_queries):
    class FakeAgent:
        called = 0

        def run(self, query, target_domain, intent, *, max_volume):
            self.called += 1
            assert target_domain == "surferseo.com"
            assert max_volume == 1500
            return VisibilityScoringResult(
                query_text=query,
                search_intent=intent,
                estimated_search_volume=2000,
                competitive_difficulty=25,
                domain_visible=True,
                visibility_position=1,
                visibility_source="fresh-test",
                opportunity_score=0.72,
                tokens_used=10,
            )

    fake = FakeAgent()
    app.extensions["scoring_agent_factory"] = lambda: fake
    before = db.session.scalar(db.select(db.func.count(DiscoveredQuery.uuid)))
    response = client.post(f"/api/v1/queries/{seeded_queries[2].uuid}/recheck")
    after = db.session.scalar(db.select(db.func.count(DiscoveredQuery.uuid)))
    assert response.status_code == 200
    assert response.json["estimated_search_volume"] == 2000
    assert response.json["domain_visible"] is True
    assert fake.called == 1
    assert before == after
