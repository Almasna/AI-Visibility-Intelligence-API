from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", "sqlite:///dev.db")
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql://", 1)
    return value


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False

    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))

    DATAFORSEO_LOGIN = os.getenv("DATAFORSEO_LOGIN")
    DATAFORSEO_PASSWORD = os.getenv("DATAFORSEO_PASSWORD")
    DATAFORSEO_BASE_URL = os.getenv(
        "DATAFORSEO_BASE_URL", "https://api.dataforseo.com"
    )
    DATAFORSEO_TIMEOUT_SECONDS = float(
        os.getenv("DATAFORSEO_TIMEOUT_SECONDS", "125")
    )
    DATAFORSEO_LOCATION_CODE = int(os.getenv("DATAFORSEO_LOCATION_CODE", "2840"))
    DATAFORSEO_LANGUAGE_CODE = os.getenv("DATAFORSEO_LANGUAGE_CODE", "en")
    DATAFORSEO_AI_MODEL = os.getenv("DATAFORSEO_AI_MODEL", "gpt-4.1-mini")
    DATAFORSEO_COUNTRY_CODE = os.getenv("DATAFORSEO_COUNTRY_CODE", "US")


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
