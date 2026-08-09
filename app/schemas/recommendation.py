from pydantic import BaseModel


class RecommendationResponse(BaseModel):
    recommendation_uuid: str
    target_query_uuid: str
    content_type: str
    title: str
    rationale: str
    target_keywords: list[str]
    priority: str
    created_at: str
