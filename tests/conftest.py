from __future__ import annotations

import pytest

from app import create_app
from app.extensions import db
from app.models import BusinessProfile


@pytest.fixture()
def app():
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test",
        }
    )
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def profile_payload():
    return {
        "name": "Surfer SEO",
        "domain": "https://www.surferseo.com/",
        "industry": "SEO Software",
        "description": "AI-powered SEO content optimization software for content teams.",
        "competitors": ["clearscope.io", "marketmuse.com", "frase.io"],
    }


@pytest.fixture()
def profile(app):
    item = BusinessProfile(
        name="Surfer SEO",
        domain="surferseo.com",
        industry="SEO Software",
        description="AI-powered SEO content optimization software for content teams.",
        competitors=["clearscope.io", "marketmuse.com"],
    )
    db.session.add(item)
    db.session.commit()
    return item
