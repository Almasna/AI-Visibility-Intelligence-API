from __future__ import annotations

from flask import current_app

from app.agents.discovery import QueryDiscoveryAgent
from app.agents.recommendation import ContentRecommendationAgent
from app.agents.scoring import VisibilityScoringAgent
from app.services.external_data import ExternalDataService
from app.services.llm import LLMService
from app.services.pipeline import PipelineService


def build_llm_service() -> LLMService:
    config = current_app.config
    return LLMService(
        provider=config["LLM_PROVIDER"],
        api_key=config.get("OPENAI_API_KEY"),
        model=config["OPENAI_MODEL"],
        timeout=config["LLM_TIMEOUT_SECONDS"],
    )


def build_external_data_service() -> ExternalDataService:
    config = current_app.config
    return ExternalDataService(
        login=config.get("DATAFORSEO_LOGIN"),
        password=config.get("DATAFORSEO_PASSWORD"),
        base_url=config["DATAFORSEO_BASE_URL"],
        timeout=config["DATAFORSEO_TIMEOUT_SECONDS"],
        location_code=config["DATAFORSEO_LOCATION_CODE"],
        language_code=config["DATAFORSEO_LANGUAGE_CODE"],
        ai_model=config["DATAFORSEO_AI_MODEL"],
        country_code=config["DATAFORSEO_COUNTRY_CODE"],
    )


def build_pipeline_service() -> PipelineService:
    factory = current_app.extensions.get("pipeline_service_factory")
    if factory is not None:
        return factory()
    llm = build_llm_service()
    external = build_external_data_service()
    return PipelineService(
        QueryDiscoveryAgent(llm),
        VisibilityScoringAgent(external),
        ContentRecommendationAgent(llm),
    )


def build_scoring_agent() -> VisibilityScoringAgent:
    factory = current_app.extensions.get("scoring_agent_factory")
    if factory is not None:
        return factory()
    return VisibilityScoringAgent(build_external_data_service())
