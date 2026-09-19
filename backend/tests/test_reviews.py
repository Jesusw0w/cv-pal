import json

import pytest
from httpx import AsyncClient

from cv_pal.constants import (
    DEFAULT_ERROR_CV_NOT_FOUND,
    DEFAULT_ERROR_LLM_INVALID_RESPONSE,
    DEFAULT_ERROR_SUGGESTION_NOT_FOUND,
)
from tests.conftest import FakeLLMClient
from tests.helpers import register_and_login, upload_cv


async def analyze(
    client: AsyncClient, headers: dict[str, str], cv_id: int
) -> list[int]:
    """Analyse a CV and return the created suggestion IDs.

    Args:
        client: The test HTTP client.
        headers: Authorization headers.
        cv_id: The CV to analyse.

    Returns:
        The IDs of the created suggestions.
    """
    response = await client.post(f"/reviews/cvs/{cv_id}/analyze", headers=headers)
    return [item["id"] for item in response.json()]


async def test_analyze_cv(client: AsyncClient, fake_llm: FakeLLMClient) -> None:
    """Analysing a CV stores the model's suggestions."""
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)

    response = await client.post(f"/reviews/cvs/{cv_id}/analyze", headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert len(data) == 2
    assert data[0]["suggestion_type"] == "content"
    assert data[0]["accepted"] is None
    assert len(fake_llm.calls) == 1


async def test_analyze_cv_sends_the_cv_text_to_the_model(
    client: AsyncClient, fake_llm: FakeLLMClient
) -> None:
    """The extracted CV text reaches the model prompt."""
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)

    await client.post(f"/reviews/cvs/{cv_id}/analyze", headers=headers)

    _system, user_prompt = fake_llm.calls[0]
    assert "CV content:" in user_prompt


async def test_analyze_cv_not_found(client: AsyncClient) -> None:
    """Analysing an unknown CV returns 404."""
    headers = await register_and_login(client)

    response = await client.post("/reviews/cvs/999/analyze", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == DEFAULT_ERROR_CV_NOT_FOUND


async def test_analyze_cv_retries_unparsable_model_output(
    client: AsyncClient, fake_llm: FakeLLMClient
) -> None:
    """Unparsable output triggers exactly one corrective retry."""
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)

    valid = fake_llm.response
    responses = iter(["not json at all", valid])

    async def flaky(*, system: str, user: str) -> str:
        fake_llm.calls.append((system, user))
        return next(responses)

    fake_llm.complete_json = flaky  # type: ignore[method-assign]

    response = await client.post(f"/reviews/cvs/{cv_id}/analyze", headers=headers)

    assert response.status_code == 201
    assert len(fake_llm.calls) == 2


async def test_analyze_cv_rejects_persistently_bad_output(
    client: AsyncClient, fake_llm: FakeLLMClient
) -> None:
    """Output that fails validation twice is rejected, not stored."""
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)
    fake_llm.response = json.dumps({"suggestions": [{"type": "nonsense"}]})

    response = await client.post(f"/reviews/cvs/{cv_id}/analyze", headers=headers)

    assert response.status_code == 502
    assert response.json()["detail"] == DEFAULT_ERROR_LLM_INVALID_RESPONSE

    stored = await client.get(f"/reviews/cvs/{cv_id}/suggestions", headers=headers)
    assert stored.json() == []


async def test_get_suggestions_empty(client: AsyncClient) -> None:
    """A CV with no analysis has no suggestions."""
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)

    response = await client.get(f"/reviews/cvs/{cv_id}/suggestions", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_get_suggestions_with_data(client: AsyncClient) -> None:
    """Stored suggestions are returned."""
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)
    await analyze(client, headers, cv_id)

    response = await client.get(f"/reviews/cvs/{cv_id}/suggestions", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.parametrize("accepted", [True, False])
async def test_set_suggestion_accepted(client: AsyncClient, accepted: bool) -> None:
    """A suggestion can be accepted or rejected."""
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)
    suggestion_id = (await analyze(client, headers, cv_id))[0]

    response = await client.patch(
        f"/reviews/suggestions/{suggestion_id}",
        headers=headers,
        json={"accepted": accepted},
    )

    assert response.status_code == 200
    assert response.json()["accepted"] is accepted


async def test_update_suggestion_not_found(client: AsyncClient) -> None:
    """Updating an unknown suggestion returns 404."""
    headers = await register_and_login(client)

    response = await client.patch(
        "/reviews/suggestions/999", headers=headers, json={"accepted": True}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == DEFAULT_ERROR_SUGGESTION_NOT_FOUND


async def test_update_suggestion_belonging_to_another_user(
    client: AsyncClient,
) -> None:
    """A user cannot change the state of someone else's suggestion."""
    owner_headers = await register_and_login(client, email="owner@example.com")
    cv_id = await upload_cv(client, owner_headers)
    suggestion_id = (await analyze(client, owner_headers, cv_id))[0]
    intruder_headers = await register_and_login(client, email="intruder@example.com")

    response = await client.patch(
        f"/reviews/suggestions/{suggestion_id}",
        headers=intruder_headers,
        json={"accepted": True},
    )

    assert response.status_code == 404


async def test_suggestions_for_another_users_cv(client: AsyncClient) -> None:
    """Suggestions cannot be listed for another user's CV."""
    owner_headers = await register_and_login(client, email="owner@example.com")
    cv_id = await upload_cv(client, owner_headers)
    intruder_headers = await register_and_login(client, email="intruder@example.com")

    response = await client.get(
        f"/reviews/cvs/{cv_id}/suggestions", headers=intruder_headers
    )

    assert response.status_code == 404
