from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class QueryListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min_score: float | None = Field(default=None, ge=0.0, le=1.0)
    status: Literal["visible", "not_visible", "unknown"] | None = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)


class PaginationParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)


class QueryResponse(BaseModel):
    query_uuid: str
    run_uuid: str
    query_text: str
    search_intent: str
    estimated_search_volume: int | None
    competitive_difficulty: float | None
    opportunity_score: float | None
    domain_visible: bool | None
    visibility_position: int | None
    visibility_source: str | None
    scoring_error: str | None
    discovered_at: str
    updated_at: str
