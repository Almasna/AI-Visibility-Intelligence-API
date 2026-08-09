from __future__ import annotations

from flask import jsonify, request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.api import api_v1
from app.extensions import db
from app.models import BusinessProfile, ContentRecommendation, DiscoveredQuery, PipelineRun
from app.schemas.profile import ProfileCreate, ProfileCreatedResponse, ProfileResponse
from app.services.dependencies import build_pipeline_service
from app.utils.errors import (
    ApiError,
    ExternalAuthenticationError,
    LLMServiceError,
)
from app.utils.http import canonical_uuid
from app.utils.time import isoformat


@api_v1.post("/profiles")
def create_profile():
    payload = request.get_json(silent=True)
    if payload is None:
        raise ApiError("INVALID_JSON", "A JSON request body is required.", 400)
    validated = ProfileCreate.model_validate(payload)
    profile = BusinessProfile(**validated.model_dump(), status="created")
    db.session.add(profile)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError(
            "PROFILE_ALREADY_EXISTS",
            "A business profile already exists for this domain.",
            409,
        ) from exc

    response = ProfileCreatedResponse(
        profile_uuid=profile.uuid,
        name=profile.name,
        domain=profile.domain,
        status=profile.status,
        created_at=isoformat(profile.created_at),
    )
    return jsonify(response.model_dump()), 201


@api_v1.get("/profiles/<profile_uuid>")
def get_profile(profile_uuid: str):
    profile = _get_profile(profile_uuid)
    total_queries = db.session.scalar(
        db.select(func.count(DiscoveredQuery.uuid)).where(
            DiscoveredQuery.profile_uuid == profile.uuid
        )
    ) or 0
    average_score = db.session.scalar(
        db.select(func.avg(DiscoveredQuery.opportunity_score)).where(
            DiscoveredQuery.profile_uuid == profile.uuid
        )
    )
    visible = db.session.scalar(
        db.select(func.count(DiscoveredQuery.uuid)).where(
            DiscoveredQuery.profile_uuid == profile.uuid,
            DiscoveredQuery.domain_visible.is_(True),
        )
    ) or 0
    not_visible = db.session.scalar(
        db.select(func.count(DiscoveredQuery.uuid)).where(
            DiscoveredQuery.profile_uuid == profile.uuid,
            DiscoveredQuery.domain_visible.is_(False),
        )
    ) or 0
    recommendation_count = db.session.scalar(
        db.select(func.count(ContentRecommendation.uuid)).where(
            ContentRecommendation.profile_uuid == profile.uuid
        )
    ) or 0
    latest = db.session.scalar(
        db.select(PipelineRun)
        .where(PipelineRun.profile_uuid == profile.uuid)
        .order_by(PipelineRun.started_at.desc())
        .limit(1)
    )
    latest_summary = None
    if latest is not None:
        latest_summary = {
            "pipeline_run_uuid": latest.uuid,
            "status": latest.status,
            "queries_discovered": latest.queries_discovered,
            "queries_scored": latest.queries_scored,
            "started_at": isoformat(latest.started_at),
            "completed_at": isoformat(latest.completed_at),
        }

    response = ProfileResponse(
        profile_uuid=profile.uuid,
        name=profile.name,
        domain=profile.domain,
        industry=profile.industry,
        description=profile.description,
        competitors=profile.competitors,
        status=profile.status,
        created_at=isoformat(profile.created_at),
        updated_at=isoformat(profile.updated_at),
        summary={
            "total_queries_discovered": total_queries,
            "average_opportunity_score": (
                round(float(average_score), 4) if average_score is not None else None
            ),
            "total_visible": visible,
            "total_not_visible": not_visible,
            "total_recommendations": recommendation_count,
            "latest_pipeline_run": latest_summary,
        },
    )
    return jsonify(response.model_dump())


@api_v1.post("/profiles/<profile_uuid>/run")
def run_pipeline(profile_uuid: str):
    profile = _get_profile(profile_uuid)
    try:
        service = build_pipeline_service()
    except (LLMServiceError, ExternalAuthenticationError) as exc:
        raise ApiError("CONFIGURATION_ERROR", str(exc), 502) from exc
    return jsonify(service.run(profile))


def _get_profile(profile_uuid: str) -> BusinessProfile:
    profile = db.session.get(BusinessProfile, canonical_uuid(profile_uuid))
    if profile is None:
        raise ApiError("PROFILE_NOT_FOUND", "Business profile not found.", 404)
    return profile
