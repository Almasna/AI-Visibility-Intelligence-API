from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SearchIntent = Literal["commercial", "comparison", "informational", "transactional"]
ContentType = Literal["blog_post", "landing_page", "comparison_page", "faq", "guide"]
Priority = Literal["high", "medium", "low"]


class DiscoveredQueryResult(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query_text: str = Field(min_length=8, max_length=300)
    intent: SearchIntent


class QueryDiscoveryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    queries: list[DiscoveredQueryResult] = Field(min_length=10, max_length=20)

    @model_validator(mode="after")
    def reject_duplicates(self) -> "QueryDiscoveryOutput":
        normalized = {
            " ".join(item.query_text.casefold().split()) for item in self.queries
        }
        if len(normalized) != len(self.queries):
            raise ValueError("Duplicate queries are not allowed.")
        return self


class RecommendationResult(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    target_query_text: str = Field(min_length=8, max_length=300)
    content_type: ContentType
    title: str = Field(min_length=8, max_length=300)
    rationale: str = Field(min_length=20, max_length=2000)
    target_keywords: list[str] = Field(min_length=2, max_length=12)
    priority: Priority

    @field_validator("target_keywords")
    @classmethod
    def unique_keywords(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            value = value.strip()
            if not value:
                raise ValueError("Keywords must not be empty.")
            key = value.casefold()
            if key not in seen:
                cleaned.append(value)
                seen.add(key)
        if len(cleaned) < 2:
            raise ValueError("At least two unique keywords are required.")
        return cleaned


class RecommendationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommendations: list[RecommendationResult] = Field(min_length=3, max_length=5)

    @model_validator(mode="after")
    def reject_duplicate_titles(self) -> "RecommendationOutput":
        titles = {item.title.casefold() for item in self.recommendations}
        if len(titles) != len(self.recommendations):
            raise ValueError("Duplicate recommendation titles are not allowed.")
        return self
