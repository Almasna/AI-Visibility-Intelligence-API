from __future__ import annotations


def test_pipeline_endpoint_uses_injected_orchestrator(app, client, profile):
    class FakePipeline:
        def run(self, received_profile):
            assert received_profile.uuid == profile.uuid
            return {
                "pipeline_run_uuid": "00000000-0000-0000-0000-000000000001",
                "status": "completed",
                "queries_discovered": 10,
                "queries_scored": 10,
                "top_opportunity_queries": [],
                "recommendations": [],
                "tokens_used": None,
            }

    app.extensions["pipeline_service_factory"] = FakePipeline
    response = client.post(f"/api/v1/profiles/{profile.uuid}/run")
    assert response.status_code == 200
    assert response.json["status"] == "completed"
    assert response.json["queries_scored"] == 10


def test_pipeline_endpoint_rejects_invalid_profile_uuid(client):
    response = client.post("/api/v1/profiles/not-a-uuid/run")
    assert response.status_code == 400
    assert response.json["error"]["code"] == "INVALID_UUID"
