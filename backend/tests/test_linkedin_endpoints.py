"""The LinkedIn import and review endpoints."""

import io
import zipfile

from httpx import AsyncClient

from tests.helpers import register_and_login
from tests.test_linkedin_parsing import REAL_EXPORT


def _archive(files: dict[str, str]) -> bytes:
    """Build a LinkedIn-shaped export archive.

    Args:
        files: Member name to CSV body.

    Returns:
        The ZIP bytes.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return buffer.getvalue()


FULL_EXPORT = _archive(
    {
        "Profile.csv": (
            "First Name,Last Name,Headline,Summary\n"
            "Inês,Marques,Senior Software Developer at Northgate Capital Markets,"
            '"Fifteen years building risk and trading systems for investment '
            "banks, lately on the platform side. I care about systems that stay "
            'explainable."\n'
        ),
        "Positions.csv": (
            "Company Name,Title,Description,Location,Started On,Finished On\n"
            "Northgate Capital Markets,Senior Software Developer,"
            '"Led the migration to event sourcing.",Lisbon,Jun 2025,\n'
        ),
        "Skills.csv": (
            "Name\nPython\nFastAPI\nAngular\nAmazon S3\nJira\nTerraform\nPostgreSQL\n"
        ),
        "Education.csv": (
            "School Name,Degree Name,Field Of Study,Start Date,End Date\n"
            "Atlântico Business School,Master's degree,Finance,2016,2018\n"
        ),
    }
)


async def test_import_requires_authentication(client: AsyncClient) -> None:
    """Nothing about a LinkedIn profile is reachable anonymously."""
    assert (await client.get("/linkedin")).status_code == 401
    assert (await client.get("/linkedin/review")).status_code == 401


async def test_review_before_any_import_is_a_404(client: AsyncClient) -> None:
    """The review says there is nothing to review rather than inventing one."""
    headers = await register_and_login(client)

    response = await client.get("/linkedin/review", headers=headers)

    assert response.status_code == 404


async def test_pasted_profile_is_imported_and_reviewed(client: AsyncClient) -> None:
    """The paste route works with no export and no file."""
    headers = await register_and_login(client)

    response = await client.post(
        "/linkedin/import", headers=headers, data={"text": REAL_EXPORT}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source"] == "paste"
    assert body["headline"] == "Senior Software Developer at Northgate Capital Markets"
    assert len(body["positions"]) == 5

    review = await client.get("/linkedin/review", headers=headers)
    assert review.status_code == 200
    assert "no section boundaries" in review.json()["note"]


async def test_export_archive_is_imported(client: AsyncClient) -> None:
    """The official archive route reads the structured files."""
    headers = await register_and_login(client)

    response = await client.post(
        "/linkedin/import",
        headers=headers,
        files={
            "file": ("Basic_LinkedInDataExport.zip", FULL_EXPORT, "application/zip")
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source"] == "export"
    assert len(body["skills"]) == 7
    assert body["about"].startswith("Fifteen years")


async def test_a_pdf_import_cannot_overwrite_the_richer_archive(
    client: AsyncClient,
) -> None:
    """The reason imports merge instead of replacing.

    LinkedIn's own PDF carries only the top three skills and no About section, so
    importing one after the data export must leave the export's data alone.
    """
    headers = await register_and_login(client)
    await client.post(
        "/linkedin/import",
        headers=headers,
        files={"file": ("export.zip", FULL_EXPORT, "application/zip")},
    )

    # The paste route stands in for the PDF here: same precision rules, no PDF bytes
    # needed. It carries three skills and no About text.
    second = await client.post(
        "/linkedin/import", headers=headers, data={"text": REAL_EXPORT}
    )

    assert second.status_code == 201
    body = second.json()
    assert len(body["skills"]) == 7, "the export's full skill list must survive"
    assert body["about"].startswith("Fifteen years"), "the export's About must survive"
    assert body["field_sources"]["skills"] == "export"
    # The positions the paste found are richer in count, but less exact, so the export
    # keeps that group too.
    assert body["field_sources"]["positions"] == "export"


async def test_a_second_import_of_equal_precision_refreshes(
    client: AsyncClient,
) -> None:
    """Re-importing the same route replaces, so a corrected profile lands."""
    headers = await register_and_login(client)
    await client.post("/linkedin/import", headers=headers, data={"text": REAL_EXPORT})

    updated = REAL_EXPORT.replace("Vantis Automotive", "Vantis Automotive Automotive")
    response = await client.post(
        "/linkedin/import", headers=headers, data={"text": updated}
    )

    assert response.status_code == 201
    employers = {p["organisation"] for p in response.json()["positions"]}
    assert "Vantis Automotive Automotive" in employers


async def test_import_rejects_neither_and_both(client: AsyncClient) -> None:
    """The route is explicit about which input it used."""
    headers = await register_and_login(client)

    assert (await client.post("/linkedin/import", headers=headers)).status_code == 400

    both = await client.post(
        "/linkedin/import",
        headers=headers,
        data={"text": REAL_EXPORT},
        files={"file": ("export.zip", FULL_EXPORT, "application/zip")},
    )
    assert both.status_code == 400


async def test_a_document_that_is_not_a_profile_is_refused(
    client: AsyncClient,
) -> None:
    """A review of the wrong document is worse than no review."""
    headers = await register_and_login(client)

    response = await client.post(
        "/linkedin/import",
        headers=headers,
        files={
            "file": ("notes.zip", _archive({"Notes.csv": "a\n1\n"}), "application/zip")
        },
    )

    assert response.status_code == 400


async def test_review_measures_coverage_against_target_roles(
    client: AsyncClient,
) -> None:
    """Recruiter-search coverage needs goals, and appears once they are set."""
    headers = await register_and_login(client)
    await client.post(
        "/linkedin/import",
        headers=headers,
        files={"file": ("export.zip", FULL_EXPORT, "application/zip")},
    )

    before = await client.get("/linkedin/review", headers=headers)
    assert before.json()["coverage"] is None

    await client.put(
        "/profile/goals",
        headers=headers,
        json={
            "target_roles": ["Python Platform Engineer"],
            "work_regimes": ["remote"],
            "regime_non_negotiable": False,
            "salary_non_negotiable": False,
        },
    )

    after = await client.get("/linkedin/review", headers=headers)
    coverage = after.json()["coverage"]
    assert coverage is not None
    assert 0 <= coverage["score"] <= 100


async def test_review_flags_a_disagreement_with_the_career_profile(
    client: AsyncClient,
) -> None:
    """A role on the career profile but not on LinkedIn is what a recruiter sees."""
    headers = await register_and_login(client)
    await client.post("/linkedin/import", headers=headers, data={"text": REAL_EXPORT})
    await client.post(
        "/profile/experiences",
        headers=headers,
        json={
            "organisation": "Somewhere Else Ltd",
            "title": "Engineer",
            "start_date": "2014-01-01",
            "end_date": "2016-01-01",
        },
    )

    response = await client.get("/linkedin/review", headers=headers)

    kinds = {issue["kind"] for issue in response.json()["consistency"]}
    assert "employer_only_on_profile" in kinds


async def test_a_snapshot_can_be_deleted(client: AsyncClient) -> None:
    """A profile export is sensitive, so removing it is a first-class action."""
    headers = await register_and_login(client)
    await client.post("/linkedin/import", headers=headers, data={"text": REAL_EXPORT})

    assert (await client.delete("/linkedin", headers=headers)).status_code == 204
    assert (await client.get("/linkedin", headers=headers)).status_code == 404


async def test_one_users_snapshot_is_invisible_to_another(client: AsyncClient) -> None:
    """Ownership is enforced, like every other record hanging off a user."""
    owner = await register_and_login(client, email="owner@example.com")
    await client.post("/linkedin/import", headers=owner, data={"text": REAL_EXPORT})

    intruder = await register_and_login(client, email="intruder@example.com")

    assert (await client.get("/linkedin", headers=intruder)).status_code == 404
