from __future__ import annotations

from app.models import ContentRecommendation, DiscoveredQuery
from app.schemas.query import QueryResponse
from app.schemas.recommendation import RecommendationResponse
from app.utils.time import isoformat


def serialize_query(query: DiscoveredQuery) -> dict:
    return QueryResponse(
        query_uuid=query.uuid,
        run_uuid=query.run_uuid,
        query_text=query.query_text,
        search_intent=query.search_intent,
        estimated_search_volume=query.estimated_search_volume,
        competitive_difficulty=query.competitive_difficulty,
        opportunity_score=query.opportunity_score,
        domain_visible=query.domain_visible,
        visibility_position=query.visibility_position,
        visibility_source=query.visibility_source,
        scoring_error=query.scoring_error,
        discovered_at=isoformat(query.discovered_at),
        updated_at=isoformat(query.updated_at),
    ).model_dump()


def serialize_recommendation(item: ContentRecommendation) -> dict:
    return RecommendationResponse(
        recommendation_uuid=item.uuid,
        target_query_uuid=item.query_uuid,
        content_type=item.content_type,
        title=item.title,
        rationale=item.rationale,
        target_keywords=item.target_keywords,
        priority=item.priority,
        created_at=isoformat(item.created_at),
    ).model_dump()
