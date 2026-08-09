from __future__ import annotations


def test_create_profile_normalizes_domain(client, profile_payload):
    response = client.post("/api/v1/profiles", json=profile_payload)
    assert response.status_code == 201
    assert response.json["domain"] == "surferseo.com"
    assert response.json["status"] == "created"


def test_invalid_profile_returns_validation_error(client, profile_payload):
    profile_payload.pop("industry")
    response = client.post("/api/v1/profiles", json=profile_payload)
    assert response.status_code == 422
    assert response.json["error"]["code"] == "VALIDATION_ERROR"


def test_invalid_json_returns_400(client):
    response = client.post(
        "/api/v1/profiles", data="not-json", content_type="application/json"
    )
    assert response.status_code == 400
    assert response.json["error"]["code"] == "INVALID_JSON"


def test_get_profile_includes_summary(client, profile_payload):
    created = client.post("/api/v1/profiles", json=profile_payload).json
    response = client.get(f"/api/v1/profiles/{created['profile_uuid']}")
    assert response.status_code == 200
    assert response.json["summary"]["total_queries_discovered"] == 0
    assert response.json["summary"]["average_opportunity_score"] is None


def test_profile_not_found(client):
    response = client.get("/api/v1/profiles/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json["error"]["code"] == "PROFILE_NOT_FOUND"


def test_duplicate_domain_is_rejected(client, profile_payload):
    assert client.post("/api/v1/profiles", json=profile_payload).status_code == 201
    response = client.post("/api/v1/profiles", json=profile_payload)
    assert response.status_code == 409
    assert response.json["error"]["code"] == "PROFILE_ALREADY_EXISTS"
