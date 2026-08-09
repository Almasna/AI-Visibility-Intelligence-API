from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.models import BusinessProfile, DiscoveredQuery
from app.schemas.agents import RecommendationOutput, RecommendationResult
from app.services.llm import LLMService
from app.utils.errors import AgentError


SYSTEM_PROMPT = """You are a senior content strategist specializing in AI-search visibility. Given a business and its highest-opportunity queries where its domain is absent, create 3-5 specific, non-duplicate content recommendations. Tie every recommendation to one supplied query exactly, propose a publishable title, explain why it closes that visibility gap, list concrete keywords/topics, and assign priority from business impact. Allowed content_type values: blog_post, landing_page, comparison_page, faq, guide. Allowed priority values: high, medium, low. Return valid JSON only, without Markdown or commentary. Exact schema: {"recommendations":[{"target_query_text":"exact supplied query","content_type":"blog_post|landing_page|comparison_page|faq|guide","title":"string","rationale":"string","target_keywords":["string","string"],"priority":"high|medium|low"}]}. Every object must contain exactly those six fields."""


class ContentRecommendationAgent(BaseAgent):
    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service
        self.last_tokens_used: int | None = None

    def run(
        self, profile: BusinessProfile, gap_queries: list[DiscoveredQuery]
    ) -> list[RecommendationResult]:
        self.last_tokens_used = None
        if not gap_queries:
            return []
        context = {
            "business": {
                "name": profile.name,
                "domain": profile.domain,
                "industry": profile.industry,
                "description": profile.description,
                "competitors": profile.competitors,
            },
            "visibility_gaps": [
                {
                    "query_text": item.query_text,
                    "intent": item.search_intent,
                    "search_volume": item.estimated_search_volume,
                    "difficulty": item.competitive_difficulty,
                    "opportunity_score": item.opportunity_score,
                }
                for item in gap_queries
            ],
        }
        result = self.llm_service.complete_json(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=(
                "Create an actionable content plan for these measured visibility gaps. "
                "Use target_query_text verbatim from the input.\n"
                + json.dumps(context, ensure_ascii=False)
            ),
        )
        self.last_tokens_used = result.total_tokens
        recommendations = self.parse_and_validate(
            result.content, RecommendationOutput
        ).recommendations
        allowed = {item.query_text for item in gap_queries}
        if any(item.target_query_text not in allowed for item in recommendations):
            raise AgentError("A recommendation referenced an unknown query.")
        return recommendations
