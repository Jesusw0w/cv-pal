"""Languages, portfolio and year-only education: what a CV needs beyond roles."""

from datetime import date

from httpx import AsyncClient

from cv_pal.analysis.extraction import extract_profile
from cv_pal.generation.tailored_cv import (
    EducationFact,
    LanguageFact,
    PortfolioFact,
    ProfileFacts,
    tailor,
)
from tests.helpers import register_and_login

POSTING = "Backend Developer. Requirements: Python and PostgreSQL."


def _profile(**sections: object) -> ProfileFacts:
    return ProfileFacts(full_name="Sam Taylor", email="sam@example.com", **sections)  # type: ignore[arg-type]


async def test_languages_are_added_listed_and_not_duplicated(
    client: AsyncClient,
) -> None:
    """A language is on the profile once, with a level."""
    headers = await register_and_login(client)

    added = await client.post(
        "/profile/languages", headers=headers, json={"name": "Dutch", "level": "native"}
    )
    again = await client.post(
        "/profile/languages", headers=headers, json={"name": "Dutch", "level": "basic"}
    )
    profile = (await client.get("/profile", headers=headers)).json()

    assert added.status_code == 201
    assert again.status_code == 400
    assert profile["languages"] == [
        {"id": added.json()["id"], "name": "Dutch", "level": "native"}
    ]


async def test_portfolio_items_are_added_and_removed(client: AsyncClient) -> None:
    """A portfolio item is a title, an optional link and a sentence."""
    headers = await register_and_login(client)

    added = await client.post(
        "/profile/portfolio",
        headers=headers,
        json={
            "title": "Tide Tables",
            "url": "example.com/tides",
            "description": "A puzzle game.",
        },
    )
    deleted = await client.delete(
        f"/profile/portfolio/{added.json()['id']}", headers=headers
    )
    profile = (await client.get("/profile", headers=headers)).json()

    assert added.status_code == 201
    assert deleted.status_code == 204
    assert profile["portfolio"] == []


async def test_education_keeps_its_date_precision(client: AsyncClient) -> None:
    """Year-only is stored as such, so no month is ever shown for it."""
    headers = await register_and_login(client)

    response = await client.post(
        "/profile/educations",
        headers=headers,
        json={
            "institution": "University of Leeds",
            "qualification": "BSc Physics",
            "start_date": "2006-01-01",
            "end_date": "2009-01-01",
            "date_precision": "year",
        },
    )

    assert response.status_code == 201
    assert response.json()["date_precision"] == "year"


def test_year_only_education_prints_no_month() -> None:
    """Years only, e.g. 2006 - 2009, and a one-year course as just its year."""
    profile = _profile(
        educations=(
            EducationFact(
                institution="University of Leeds",
                qualification="BSc Physics",
                start_date=date(2006, 1, 1),
                end_date=date(2009, 1, 1),
                year_only=True,
            ),
            EducationFact(
                institution="Open Academy",
                qualification="Certificate in Statistics",
                start_date=date(2011, 1, 1),
                end_date=date(2011, 1, 1),
                year_only=True,
            ),
        )
    )

    text = tailor(profile, POSTING).markdown

    assert "2006 - 2009" in text
    assert "Jan 2006" not in text
    assert "2011" in text
    assert "2011 - 2011" not in text


def test_month_precision_education_still_shows_months() -> None:
    """The default is unchanged: months known are months shown."""
    profile = _profile(
        educations=(
            EducationFact(
                institution="University of Leeds",
                qualification="MSc Physics",
                start_date=date(2010, 9, 1),
                end_date=date(2011, 7, 1),
            ),
        )
    )

    assert "Sep 2010" in tailor(profile, POSTING).markdown


def test_languages_and_portfolio_appear_on_the_cv() -> None:
    """Both sections are printed, with the link where there is one."""
    profile = _profile(
        languages=(LanguageFact("Dutch", "native"), LanguageFact("German", "fluent")),
        portfolio=(
            PortfolioFact("Tide Tables", "example.com/tides", "A puzzle game."),
        ),
    )

    text = tailor(profile, POSTING).markdown

    assert "## Languages" in text
    assert "Dutch (native)" in text
    assert "German (fluent)" in text
    assert "## Portfolio" in text
    assert "example.com/tides" in text


def test_languages_are_read_from_a_cv_with_their_level() -> None:
    """Both layouts: a labelled line, and a heading with the list under it."""
    labelled = extract_profile(
        "SKILLS\nLanguages: Dutch (native), German (fluent, daily use), Italian (B1)\n"
    )
    headed = extract_profile("LANGUAGES\nDutch (native), German(ﬂuent)\n")

    assert [(lang.name, lang.level.value) for lang in labelled.languages] == [
        ("Dutch", "native"),
        ("German", "fluent"),
        ("Italian", "intermediate"),
    ]
    assert [(lang.name, lang.level.value) for lang in headed.languages] == [
        ("Dutch", "native"),
        ("German", "fluent"),
    ]


def test_a_language_list_without_levels_is_not_proposed() -> None:
    """A "Languages:" line listing Python and Go is not about spoken languages."""
    assert extract_profile("SKILLS\nLanguages: Python, Go, Rust\n").languages == ()
