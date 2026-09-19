from httpx import AsyncClient

from cv_pal.constants import DEFAULT_ERROR_CV_NOT_FOUND
from tests.helpers import register_and_login, upload_cv

JOB_DESCRIPTION = """
Backend Engineer

Requirements:
- Strong Python and PostgreSQL experience
- Kubernetes in production

Nice to have:
- Terraform
"""


async def test_ats_check_returns_a_report(client: AsyncClient) -> None:
    """The check runs against an uploaded CV and returns a score."""
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)

    response = await client.post(f"/analysis/cvs/{cv_id}/ats-check", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["score"] <= 100
    assert "findings" in body


async def test_ats_check_flags_an_unreadable_cv(client: AsyncClient) -> None:
    """A CV with no extractable text is reported as blocking.

    The helper uploads a blank single-page PDF, which is exactly the scanned-CV case:
    a valid file that yields no text.
    """
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)

    body = (
        await client.post(f"/analysis/cvs/{cv_id}/ats-check", headers=headers)
    ).json()

    assert {f["code"] for f in body["blocking"]} == {"no_text"}
    assert body["score"] == 0


async def test_ats_check_requires_ownership(client: AsyncClient) -> None:
    """Another user's CV cannot be analysed."""
    owner = await register_and_login(client, email="owner@example.com")
    cv_id = await upload_cv(client, owner)
    intruder = await register_and_login(client, email="intruder@example.com")

    response = await client.post(f"/analysis/cvs/{cv_id}/ats-check", headers=intruder)

    assert response.status_code == 404
    assert response.json()["detail"] == DEFAULT_ERROR_CV_NOT_FOUND


async def test_ats_check_requires_authentication(client: AsyncClient) -> None:
    """The endpoint is not anonymous."""
    response = await client.post("/analysis/cvs/1/ats-check")

    assert response.status_code == 401


async def test_coverage_returns_matched_and_missing(client: AsyncClient) -> None:
    """Scoring against a posting reports both sides, not just a number."""
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)

    response = await client.post(
        f"/analysis/cvs/{cv_id}/coverage",
        headers=headers,
        json={"job_description": JOB_DESCRIPTION},
    )

    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["score"] <= 100
    assert {"matched", "missing", "missing_required"} <= body.keys()
    assert "kubernetes" in {k["term"] for k in body["missing"]}


async def test_coverage_separates_required_gaps(client: AsyncClient) -> None:
    """Unmet requirements are distinguishable from unmet bonuses."""
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)

    body = (
        await client.post(
            f"/analysis/cvs/{cv_id}/coverage",
            headers=headers,
            json={"job_description": JOB_DESCRIPTION},
        )
    ).json()

    required_terms = {k["term"] for k in body["missing_required"]}
    assert "kubernetes" in required_terms
    assert "terraform" not in required_terms


async def test_coverage_rejects_an_empty_job_description(client: AsyncClient) -> None:
    """A blank posting is a validation error, not a meaningless score."""
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)

    response = await client.post(
        f"/analysis/cvs/{cv_id}/coverage",
        headers=headers,
        json={"job_description": "  "},
    )

    assert response.status_code == 422


async def test_coverage_requires_ownership(client: AsyncClient) -> None:
    """Another user's CV cannot be scored."""
    owner = await register_and_login(client, email="owner@example.com")
    cv_id = await upload_cv(client, owner)
    intruder = await register_and_login(client, email="intruder@example.com")

    response = await client.post(
        f"/analysis/cvs/{cv_id}/coverage",
        headers=intruder,
        json={"job_description": JOB_DESCRIPTION},
    )

    assert response.status_code == 404


async def test_analysis_needs_no_language_model(
    client: AsyncClient, fake_llm: object
) -> None:
    """Neither endpoint touches the model.

    This is the whole point of the deterministic core: the analysis works with no
    provider configured at all.
    """
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)

    await client.post(f"/analysis/cvs/{cv_id}/ats-check", headers=headers)
    await client.post(
        f"/analysis/cvs/{cv_id}/coverage",
        headers=headers,
        json={"job_description": JOB_DESCRIPTION},
    )

    assert fake_llm.calls == []  # type: ignore[attr-defined]
