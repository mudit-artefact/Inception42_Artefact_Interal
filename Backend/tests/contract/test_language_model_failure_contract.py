"""An unreachable language model must be reported as a service problem, not a 200."""

import pytest

pytestmark = pytest.mark.contract


def test_the_endpoint_reports_a_service_problem_when_the_model_is_unreachable(
    api_client, fake_language_model, stub_policy_search_service
):
    fake_language_model.fail_every_call_with(RuntimeError("the model is unreachable"))

    response = api_client.post(
        "/api/v1/hcs01/query", json={"message": "What is the weather in Dubai?"}
    )

    assert response.status_code == 503
    # The web interface reads its error text from this key.
    assert "detail" in response.json()
