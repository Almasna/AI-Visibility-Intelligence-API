from __future__ import annotations

from flask import jsonify, request
from sqlalchemy import func

from app.api import api_v1
from app.extensions import db
from app.models import BusinessProfile, ContentRecommendation, DiscoveredQuery
from app.schemas.query import PaginationParams, QueryListParams
from app.schemas.serialization import serialize_query, serialize_recommendation
from app.services.dependencies import build_scoring_agent
from app.utils.errors import ApiError, ExternalAuthenticationError, ExternalDataError
from app.utils.http import canonical_uuid


@api_v1.get("/profiles/<profile_uuid>/queries")
def list_queries(profile_uuid: str):
    profile = _get_profile(profile_uuid)
    params = QueryListParams.model_validate(request.args.to_dict())
    statement = db.select(DiscoveredQuery).where(
        DiscoveredQuery.profile_uuid == profile.uuid
    )
    if params.min_score is not None:
        statement = statement.where(
            DiscoveredQuery.opportunity_score >= params.min_score
        )
    if params.status == "visible":
        statement = statement.where(DiscoveredQuery.domain_visible.is_(True))
    elif params.status == "not_visible":
        statement = statement.where(DiscoveredQuery.domain_visible.is_(False))
    elif params.status == "unknown":
        statement = statement.where(DiscoveredQuery.domain_visible.is_(None))
    statement = statement.order_by(
        DiscoveredQuery.opportunity_score.is_(None),
        DiscoveredQuery.opportunity_score.desc(),
        DiscoveredQuery.discovered_at.desc(),
    )
    pagination = db.paginate(
        statement, page=params.page, per_page=params.per_page, error_out=False
    )
    return jsonify(
        {
            "items": [serialize_query(item) for item in pagination.items],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total_items": pagination.total,
                "total_pages": pagination.pages,
            },
        }
    )


@api_v1.get("/profiles/<profile_uuid>/recommendations")
def list_recommendations(profile_uuid: str):
    profile = _get_profile(profile_uuid)
    params = PaginationParams.model_validate(request.args.to_dict())
    statement = (
        db.select(ContentRecommendation)
        .where(ContentRecommendation.profile_uuid == profile.uuid)
        .order_by(ContentRecommendation.created_at.desc())
    )
    pagination = db.paginate(
        statement, page=params.page, per_page=params.per_page, error_out=False
    )
    return jsonify(
        {
            "items": [
                serialize_recommendation(item) for item in pagination.items
            ],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total_items": pagination.total,
                "total_pages": pagination.pages,
            },
        }
    )


@api_v1.post("/queries/<query_uuid>/recheck")
def recheck_query(query_uuid: str):
    query = db.session.get(DiscoveredQuery, canonical_uuid(query_uuid))
    if query is None:
        raise ApiError("QUERY_NOT_FOUND", "Discovered query not found.", 404)
    profile = db.session.get(BusinessProfile, query.profile_uuid)
    max_volume = db.session.scalar(
        db.select(func.max(DiscoveredQuery.estimated_search_volume)).where(
            DiscoveredQuery.run_uuid == query.run_uuid
        )
    )
    try:
        agent = build_scoring_agent()
        result = agent.run(
            query.query_text,
            profile.domain,
            query.search_intent,
            max_volume=max_volume,
        )
    except ExternalAuthenticationError as exc:
        raise ApiError("CONFIGURATION_ERROR", str(exc), 502) from exc
    except ExternalDataError as exc:
        raise ApiError("EXTERNAL_PROVIDER_ERROR", str(exc), 502) from exc

    query.estimated_search_volume = result.estimated_search_volume
    query.competitive_difficulty = result.competitive_difficulty
    query.opportunity_score = result.opportunity_score
    query.domain_visible = result.domain_visible
    query.visibility_position = result.visibility_position
    query.visibility_source = result.visibility_source
    query.scoring_error = None
    db.session.commit()
    return jsonify(serialize_query(query))


def _get_profile(profile_uuid: str) -> BusinessProfile:
    profile = db.session.get(BusinessProfile, canonical_uuid(profile_uuid))
    if profile is None:
        raise ApiError("PROFILE_NOT_FOUND", "Business profile not found.", 404)
    return profile
