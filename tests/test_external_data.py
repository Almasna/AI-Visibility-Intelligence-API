from __future__ import annotations

import pytest
import requests

from app.services.external_data import ExternalDataService
from app.utils.errors import ExternalAuthenticationError, ExternalDataError


class FakeResponse:
    def __init__(self, body, status_code=200):
        self._body = body
        self.status_code = status_code
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.responses.pop(0)


def success_task(result):
    return {
        "status_code": 20000,
        "status_message": "Ok.",
        "tasks": [
            {"status_code": 20000, "status_message": "Ok.", "result": result}
        ],
    }


def service(session):
    return ExternalDataService(login="login", password="password", session=session)


def test_google_ads_contract_is_parsed_and_long_question_is_mapped():
    session = FakeSession(
        [
            FakeResponse(
                success_task(
                    [
                        {
                            "keyword": "which seo tool is best for a large content marketing",
                            "search_volume": 1200,
                            "competition_index": 62,
                        }
                    ]
                )
            )
        ]
    )
    query = "Which SEO tool is best for a large content marketing team today?"
    metrics = service(session).get_keyword_metrics([query])[query]
    assert metrics.search_volume == 1200
    assert metrics.competitive_difficulty == 62
    url, kwargs = session.calls[0]
    assert url.endswith("/v3/keywords_data/google_ads/search_volume/live")
    assert kwargs["auth"] == ("login", "password")
    assert len(kwargs["json"][0]["keywords"][0].split()) <= 10


def test_ai_visibility_uses_ordered_annotation_domains():
    response = success_task(
        [
            {
                "input_tokens": 100,
                "output_tokens": 20,
                "items": [
                    {
                        "type": "message",
                        "sections": [
                            {
                                "type": "text",
                                "text": "Here are current options.",
                                "annotations": [
                                    {"url": "https://competitor.com/article"},
                                    {"url": "https://www.example.com/guide"},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    )
    result = service(FakeSession([FakeResponse(response)])).check_ai_visibility(
        "What is the best platform?", "example.com"
    )
    assert result.domain_visible is True
    assert result.visibility_position == 2
    assert result.tokens_used == 120


def test_ai_visibility_false_when_domain_absent():
    response = success_task(
        [
            {
                "items": [
                    {
                        "type": "message",
                        "sections": [
                            {
                                "text": "Only another source is cited.",
                                "annotations": [{"url": "https://other.com/page"}],
                            }
                        ],
                    }
                ]
            }
        ]
    )
    result = service(FakeSession([FakeResponse(response)])).check_ai_visibility(
        "What is the best platform?", "example.com"
    )
    assert result.domain_visible is False
    assert result.visibility_position is None


def test_provider_authentication_error_is_controlled():
    with pytest.raises(ExternalAuthenticationError):
        service(FakeSession([FakeResponse({}, status_code=401)])).get_keyword_metrics(
            ["seo tool"]
        )


def test_provider_timeout_is_controlled():
    with pytest.raises(ExternalDataError, match="timed out"):
        service(FakeSession(error=requests.Timeout())).get_keyword_metrics(["seo tool"])
