from __future__ import annotations

import logging
from time import monotonic

from app.agents.discovery import QueryDiscoveryAgent
from app.agents.recommendation import ContentRecommendationAgent
from app.agents.scoring import QueryCandidate, VisibilityScoringAgent
from app.extensions import db
from app.models import (
    BusinessProfile,
    ContentRecommendation,
    DiscoveredQuery,
    PipelineRun,
)
from app.schemas.serialization import serialize_query, serialize_recommendation
from app.utils.errors import ApiError
from app.utils.time import utcnow


logger = logging.getLogger(__name__)


class PipelineService:
    def __init__(
        self,
        discovery_agent: QueryDiscoveryAgent,
        scoring_agent: VisibilityScoringAgent,
        recommendation_agent: ContentRecommendationAgent,
    ) -> None:
        self.discovery_agent = discovery_agent
        self.scoring_agent = scoring_agent
        self.recommendation_agent = recommendation_agent

    def run(self, profile: BusinessProfile) -> dict:
        pipeline_run = PipelineRun(profile_uuid=profile.uuid, status="running")
        profile.status = "running"
        db.session.add(pipeline_run)
        db.session.commit()
        context = {
            "pipeline_run_uuid": pipeline_run.uuid,
            "profile_uuid": profile.uuid,
        }
        logger.info("pipeline_started %s", context)

        try:
            started = monotonic()
            logger.info("agent_1_started %s", context)
            discovered = self.discovery_agent.run(profile)
            logger.info(
                "agent_1_completed %s",
                {**context, "count": len(discovered), "duration": monotonic() - started},
            )
        except Exception as exc:
            logger.exception("agent_1_failed %s", context)
            self._fail(pipeline_run, profile, f"Query discovery failed: {exc}")
            raise ApiError(
                "PIPELINE_FAILED",
                "Query discovery failed; the pipeline run was recorded.",
                502,
                {"pipeline_run_uuid": pipeline_run.uuid, "status": "failed"},
            ) from exc

        query_models = [
            DiscoveredQuery(
                profile_uuid=profile.uuid,
                run_uuid=pipeline_run.uuid,
                query_text=item.query_text,
                search_intent=item.intent,
            )
            for item in discovered
        ]
        db.session.add_all(query_models)
        pipeline_run.queries_discovered = len(query_models)
        pipeline_run.tokens_used = self.discovery_agent.last_tokens_used
        db.session.commit()

        logger.info("agent_2_started %s", context)
        started = monotonic()
        candidates = [
            QueryCandidate(query_text=item.query_text, intent=item.search_intent)
            for item in query_models
        ]
        try:
            scoring = self.scoring_agent.run_batch(candidates, profile.domain)
        except Exception as exc:
            logger.exception("agent_2_batch_failed %s", context)
            scoring = None
            for item in query_models:
                item.scoring_error = "Visibility scoring could not be completed."
            db.session.commit()
            self._fail(pipeline_run, profile, f"Visibility scoring failed: {exc}")
            raise ApiError(
                "PIPELINE_FAILED",
                "Visibility scoring failed; discovered queries were preserved.",
                502,
                {"pipeline_run_uuid": pipeline_run.uuid, "status": "failed"},
            ) from exc

        total_tokens = pipeline_run.tokens_used
        for query_model in query_models:
            result = scoring.successes.get(query_model.query_text)
            if result is None:
                query_model.scoring_error = scoring.failures.get(
                    query_model.query_text, "Visibility scoring failed."
                )
                logger.warning(
                    "agent_2_query_failed %s",
                    {**context, "query_uuid": query_model.uuid},
                )
                continue
            query_model.estimated_search_volume = result.estimated_search_volume
            query_model.competitive_difficulty = result.competitive_difficulty
            query_model.opportunity_score = result.opportunity_score
            query_model.domain_visible = result.domain_visible
            query_model.visibility_position = result.visibility_position
            query_model.visibility_source = result.visibility_source
            query_model.scoring_error = None
            total_tokens = _add_tokens(total_tokens, result.tokens_used)

        pipeline_run.queries_scored = len(scoring.successes)
        pipeline_run.tokens_used = total_tokens
        db.session.commit()
        logger.info(
            "agent_2_completed %s",
            {
                **context,
                "scored": len(scoring.successes),
                "failed": len(scoring.failures),
                "duration": monotonic() - started,
            },
        )

        if not scoring.successes:
            self._fail(
                pipeline_run,
                profile,
                "No queries could be scored by the external provider.",
            )
            raise ApiError(
                "PIPELINE_FAILED",
                "No query could be scored; discovered queries and errors were preserved.",
                502,
                {"pipeline_run_uuid": pipeline_run.uuid, "status": "failed"},
            )

        scored_models = [item for item in query_models if item.opportunity_score is not None]
        scored_models.sort(key=lambda item: item.opportunity_score or 0.0, reverse=True)
        gap_queries = [item for item in scored_models if item.domain_visible is False][:5]

        recommendation_failed = False
        recommendations: list[ContentRecommendation] = []
        logger.info("agent_3_started %s", {**context, "gaps": len(gap_queries)})
        started = monotonic()
        try:
            generated = self.recommendation_agent.run(profile, gap_queries)
            query_by_text = {item.query_text: item for item in gap_queries}
            recommendations = [
                ContentRecommendation(
                    profile_uuid=profile.uuid,
                    query_uuid=query_by_text[item.target_query_text].uuid,
                    content_type=item.content_type,
                    title=item.title,
                    rationale=item.rationale,
                    target_keywords=item.target_keywords,
                    priority=item.priority,
                )
                for item in generated
            ]
            db.session.add_all(recommendations)
            pipeline_run.tokens_used = _add_tokens(
                pipeline_run.tokens_used, self.recommendation_agent.last_tokens_used
            )
            db.session.commit()
            logger.info(
                "agent_3_completed %s",
                {
                    **context,
                    "count": len(recommendations),
                    "duration": monotonic() - started,
                },
            )
        except Exception as exc:
            db.session.rollback()
            recommendation_failed = True
            logger.warning("agent_3_failed %s", context, exc_info=True)
            pipeline_run = db.session.get(PipelineRun, pipeline_run.uuid)
            profile = db.session.get(BusinessProfile, profile.uuid)
            pipeline_run.error_message = f"Content recommendation failed: {exc}"[:4000]

        partial = bool(scoring.failures) or recommendation_failed
        pipeline_run.status = "partially_completed" if partial else "completed"
        profile.status = pipeline_run.status
        if scoring.failures and not pipeline_run.error_message:
            pipeline_run.error_message = (
                f"{len(scoring.failures)} query scoring operation(s) failed."
            )
        pipeline_run.completed_at = utcnow()
        db.session.commit()
        logger.info("pipeline_completed %s", {**context, "status": pipeline_run.status})

        return {
            "pipeline_run_uuid": pipeline_run.uuid,
            "status": pipeline_run.status,
            "queries_discovered": pipeline_run.queries_discovered,
            "queries_scored": pipeline_run.queries_scored,
            "top_opportunity_queries": [
                serialize_query(item) for item in scored_models[:3]
            ],
            "recommendations": [
                serialize_recommendation(item) for item in recommendations
            ],
            "tokens_used": pipeline_run.tokens_used,
        }

    @staticmethod
    def _fail(
        pipeline_run: PipelineRun, profile: BusinessProfile, message: str
    ) -> None:
        pipeline_run.status = "failed"
        pipeline_run.error_message = message[:4000]
        pipeline_run.completed_at = utcnow()
        profile.status = "failed"
        db.session.commit()
        logger.error(
            "pipeline_failed %s",
            {
                "pipeline_run_uuid": pipeline_run.uuid,
                "profile_uuid": profile.uuid,
            },
        )


def _add_tokens(current: int | None, additional: int | None) -> int | None:
    if additional is None:
        return current
    return (current or 0) + additional
