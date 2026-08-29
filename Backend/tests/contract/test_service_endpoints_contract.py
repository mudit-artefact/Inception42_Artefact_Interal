"""Pins the supporting endpoints: health, the policy catalogue, and the root banner."""

import pytest

pytestmark = pytest.mark.contract


def test_health_reports_service_and_index_state(api_client):
    response = api_client.get("/api/v1/hcs01/health")

    assert response.status_code == 200, response.text
    body = response.json()
    assert {
        "status",
        "service",
        "version",
        "qdrant_connected",
        "vectors_indexed",
        "llm_model",
        "embedding_model",
    } == set(body)
    assert body["status"] in {"ok", "degraded"}


def test_policy_catalogue_lists_every_english_policy_with_pdf_links(api_client):
    response = api_client.get("/api/v1/hcs01/policies")

    assert response.status_code == 200, response.text
    policies = response.json()
    assert len(policies) == 9
    for policy in policies:
        assert {"id", "title", "section", "topics", "pdf_url", "url", "diagram_page"} == set(policy)
        assert policy["pdf_url"].startswith("/api/v1/hcs01/policies/pdf/"), (
            "the frontend builds deep links from this prefix"
        )


def test_root_banner_still_answers(api_client):
    response = api_client.get("/")
    assert response.status_code == 200
    assert response.json()["service"]


def test_reindexing_is_available_as_a_post(api_client, fake_embedding_model):
    """Rebuilding an index changes state, so it belongs behind POST, not GET."""
    response = api_client.post("/api/v1/hcs01/policies/reindex")

    assert response.status_code == 200, response.text
    assert response.json()["status"] in {"success", "skipped"}


def test_rebuilding_the_index_can_be_forced(api_client, fake_embedding_model):
    """Defect 1: this used to be a guaranteed 500, because the indexing function took no
    `force` parameter while the endpoint passed one."""
    response = api_client.post("/api/v1/hcs01/policies/reindex?force=true")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    assert body["chunks_indexed"] == 121
