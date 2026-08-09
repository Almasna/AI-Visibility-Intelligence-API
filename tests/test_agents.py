from __future__ import annotations

import json

import pytest

from app.agents.discovery import QueryDiscoveryAgent
from app.agents.recommendation import ContentRecommendationAgent
from app.models import DiscoveredQuery
from app.services.llm import LLMResult
from app.utils.errors import AgentError


class StubLLM:
    def __init__(self, content: str):
        self.content = content

    def complete_json(self, **_):
        return LLMResult(self.content, total_tokens=42)


def discovery_payload():
    intents = ["commercial", "comparison", "informational", "transactional"]
    return {
        "queries": [
            {
                "query_text": f"Which SEO optimization tool is best for use case {i}?",
                "intent": intents[i % 4],
            }
            for i in range(10)
        ]
    }


def recommendation_payload(query_text: str):
    return {
        "recommendations": [
            {
                "target_query_text": query_text,
                "content_type": content_type,
                "title": f"A specific publishable SEO title number {index}",
                "rationale": "This directly addresses the measured high-opportunity visibility gap.",
                "target_keywords": ["seo software", f"content optimization {index}"],
                "priority": "high" if index == 1 else "medium",
            }
            for index, content_type in enumerate(
                ["blog_post", "comparison_page", "guide"], start=1
            )
        ]
    }


def test_discovery_agent_valid_response(profile):
    agent = QueryDiscoveryAgent(StubLLM(json.dumps(discovery_payload())))
    result = agent.run(profile)
    assert len(result) == 10
    assert agent.last_tokens_used == 42


def test_discovery_agent_malformed_json(profile):
    with pytest.raises(AgentError):
        QueryDiscoveryAgent(StubLLM("not json")).run(profile)


def test_discovery_agent_missing_fields(profile):
    payload = discovery_payload()
    payload["queries"][0].pop("intent")
    with pytest.raises(AgentError):
        QueryDiscoveryAgent(StubLLM(json.dumps(payload))).run(profile)


def test_discovery_agent_rejects_duplicates(profile):
    payload = discovery_payload()
    payload["queries"][1] = payload["queries"][0]
    with pytest.raises(AgentError):
        QueryDiscoveryAgent(StubLLM(json.dumps(payload))).run(profile)


def test_recommendation_agent_valid_response(profile):
    query = DiscoveredQuery(
        profile_uuid=profile.uuid,
        run_uuid="00000000-0000-0000-0000-000000000001",
        query_text="What is the best SEO content optimization platform?",
        search_intent="commercial",
        estimated_search_volume=1200,
        competitive_difficulty=60,
        opportunity_score=0.8,
        domain_visible=False,
    )
    agent = ContentRecommendationAgent(
        StubLLM(json.dumps(recommendation_payload(query.query_text)))
    )
    assert len(agent.run(profile, [query])) == 3


@pytest.mark.parametrize(
    "content",
    ["not-json", json.dumps({"recommendations": [{"content_type": "tweet"}]})],
)
def test_recommendation_agent_rejects_bad_output(profile, content):
    query = DiscoveredQuery(
        query_text="What is the best SEO content optimization platform?",
        search_intent="commercial",
    )
    with pytest.raises(AgentError):
        ContentRecommendationAgent(StubLLM(content)).run(profile, [query])
