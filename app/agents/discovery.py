from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.models import BusinessProfile
from app.schemas.agents import DiscoveredQueryResult, QueryDiscoveryOutput
from app.services.llm import LLMService


SYSTEM_PROMPT = """You are a senior AI-search query strategist. Generate realistic questions a buyer would ask an AI assistant while evaluating products or services in the supplied business market. Return 10-20 unique natural-language questions. Favor commercial, comparison, and transactional value while retaining useful informational questions. Cover category discovery, alternatives, comparisons, use cases, objections, and buying decisions. Never duplicate or lightly rephrase a question. Return valid JSON only, without Markdown or commentary. Exact schema: {"queries":[{"query_text":"string","intent":"commercial|comparison|informational|transactional"}]}. Every object must contain exactly those two fields."""


class QueryDiscoveryAgent(BaseAgent):
    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service
        self.last_tokens_used: int | None = None

    def run(self, profile: BusinessProfile) -> list[DiscoveredQueryResult]:
        context = {
            "business_name": profile.name,
            "domain": profile.domain,
            "industry": profile.industry,
            "description": profile.description,
            "competitors": profile.competitors,
        }
        user_prompt = (
            "Create the query set for this business context. Questions must be "
            "commercially relevant to this exact market and suitable for measuring AI "
            "visibility. Business context:\n" + json.dumps(context, ensure_ascii=False)
        )
        result = self.llm_service.complete_json(
            system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt
        )
        self.last_tokens_used = result.total_tokens
        return self.parse_and_validate(result.content, QueryDiscoveryOutput).queries
