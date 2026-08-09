from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agents import SearchIntent
from app.services.external_data import ExternalDataService, SearchMetrics, VisibilityResult
from app.utils.errors import ExternalDataError
from app.utils.scoring import calculate_opportunity_score


class VisibilityScoringResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query_text: str
    search_intent: SearchIntent
    estimated_search_volume: int = Field(ge=0)
    competitive_difficulty: float = Field(ge=0, le=100)
    domain_visible: bool
    visibility_position: int | None = Field(default=None, ge=1)
    visibility_source: str
    opportunity_score: float = Field(ge=0, le=1)
    tokens_used: int | None = Field(default=None, ge=0)


@dataclass(frozen=True)
class QueryCandidate:
    query_text: str
    intent: SearchIntent


@dataclass
class ScoringBatchResult:
    successes: dict[str, VisibilityScoringResult]
    failures: dict[str, str]


class VisibilityScoringAgent:
    def __init__(self, external_data_service: ExternalDataService) -> None:
        self.external_data_service = external_data_service

    def run_batch(
        self, candidates: list[QueryCandidate], target_domain: str
    ) -> ScoringBatchResult:
        try:
            metrics = self.external_data_service.get_keyword_metrics(
                [item.query_text for item in candidates]
            )
        except ExternalDataError as exc:
            return ScoringBatchResult(
                successes={},
                failures={item.query_text: str(exc) for item in candidates},
            )

        raw_successes: list[
            tuple[QueryCandidate, SearchMetrics, VisibilityResult]
        ] = []
        failures: dict[str, str] = {}
        for candidate in candidates:
            metric = metrics.get(candidate.query_text)
            if metric is None:
                failures[candidate.query_text] = (
                    "DataForSEO returned no complete keyword metrics."
                )
                continue
            try:
                visibility = self.external_data_service.check_ai_visibility(
                    candidate.query_text, target_domain
                )
            except ExternalDataError as exc:
                failures[candidate.query_text] = str(exc)
                continue
            raw_successes.append((candidate, metric, visibility))

        max_volume = max(
            (metric.search_volume for _, metric, _ in raw_successes), default=0
        )
        successes: dict[str, VisibilityScoringResult] = {}
        for candidate, metric, visibility in raw_successes:
            successes[candidate.query_text] = VisibilityScoringResult(
                query_text=candidate.query_text,
                search_intent=candidate.intent,
                estimated_search_volume=metric.search_volume,
                competitive_difficulty=metric.competitive_difficulty,
                domain_visible=visibility.domain_visible,
                visibility_position=visibility.visibility_position,
                visibility_source=visibility.source,
                opportunity_score=calculate_opportunity_score(
                    metric.search_volume,
                    metric.competitive_difficulty,
                    visibility.domain_visible,
                    candidate.intent,
                    max_volume,
                ),
                tokens_used=visibility.tokens_used,
            )
        return ScoringBatchResult(successes=successes, failures=failures)

    def run(
        self,
        query: str,
        target_domain: str,
        intent: SearchIntent,
        *,
        max_volume: int | None = None,
    ) -> VisibilityScoringResult:
        metrics = self.external_data_service.get_keyword_metrics([query]).get(query)
        if metrics is None:
            raise ExternalDataError("DataForSEO returned no complete keyword metrics.")
        visibility = self.external_data_service.check_ai_visibility(query, target_domain)
        normalization_max = max(max_volume or 0, metrics.search_volume)
        return VisibilityScoringResult(
            query_text=query,
            search_intent=intent,
            estimated_search_volume=metrics.search_volume,
            competitive_difficulty=metrics.competitive_difficulty,
            domain_visible=visibility.domain_visible,
            visibility_position=visibility.visibility_position,
            visibility_source=visibility.source,
            opportunity_score=calculate_opportunity_score(
                metrics.search_volume,
                metrics.competitive_difficulty,
                visibility.domain_visible,
                intent,
                normalization_max,
            ),
            tokens_used=visibility.tokens_used,
        )
