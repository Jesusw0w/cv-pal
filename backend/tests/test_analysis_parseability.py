from cv_pal.analysis.parseability import check_parseability
from cv_pal.constants import ParseabilitySeverity

GOOD_CV = """
Jane Doe
jane.doe@example.com | +44 7700 900123

Experience
- Led migration of 40 services to Kubernetes, cutting deploy time by 60%
- Built a data pipeline processing 2M events per day
- Reduced infrastructure spend by 35% across 2021 and 2022

Education
BSc Computer Science, University of Manchester, 2016

Skills
Python, PostgreSQL, Docker, Terraform
"""


def codes(text: str) -> set[str]:
    """Return the finding codes produced for a CV.

    Args:
        text: The CV text.

    Returns:
        The set of codes.
    """
    return {finding.code for finding in check_parseability(text).findings}


def test_a_well_formed_cv_scores_highly() -> None:
    """A single-column CV with contacts, sections and dates passes cleanly."""
    report = check_parseability(GOOD_CV)

    assert report.score >= 90
    assert report.blocking == ()


def test_empty_text_is_a_blocking_error() -> None:
    """A scanned CV extracts to nothing, which is fatal for an ATS."""
    report = check_parseability("")

    assert report.score == 0
    assert report.word_count == 0
    assert {f.code for f in report.blocking} == {"no_text"}


def test_missing_email_is_blocking() -> None:
    """Contact details that do not survive extraction cannot be used."""
    without_email = GOOD_CV.replace("jane.doe@example.com | ", "")

    assert "no_email" in codes(without_email)
    assert any(
        f.severity is ParseabilitySeverity.ERROR
        for f in check_parseability(without_email).findings
        if f.code == "no_email"
    )


def test_missing_dates_is_blocking() -> None:
    """Without machine-readable dates an ATS cannot compute experience."""
    undated = """
    Jane Doe
    jane.doe@example.com

    Experience
    - Led a migration recently
    - Built a pipeline a couple of years ago

    Education
    BSc Computer Science

    Skills
    Python
    """

    assert "no_parseable_dates" in codes(undated)


def test_detects_missing_sections() -> None:
    """Unlabelled blocks of text are flagged per missing heading."""
    found = codes("Jane Doe\njane@example.com\nDid things in 2021.\n" * 40)

    assert "missing_section_experience" in found
    assert "missing_section_education" in found
    assert "missing_section_skills" in found


def test_detects_a_fragmented_layout() -> None:
    """Many very short lines is what a column layout looks like after extraction."""
    columns = "Jane Doe\njane@example.com\n2021\n" + "\n".join(
        ["Python", "AWS", "SQL"] * 30
    )

    assert "fragmented_layout" in codes(columns)


def test_a_prose_cv_is_not_flagged_as_fragmented() -> None:
    """Normal bullet prose must not trip the column heuristic."""
    assert "fragmented_layout" not in codes(GOOD_CV)


def test_flags_a_very_short_cv() -> None:
    """Too little text usually means extraction lost most of it."""
    assert "too_short" in codes(GOOD_CV)


def test_flags_a_very_long_cv() -> None:
    """Length is advisory, not blocking."""
    long_cv = GOOD_CV + (
        "\n- Delivered another project in 2020 with measurable impact" * 300
    )
    report = check_parseability(long_cv)

    assert "too_long" in {f.code for f in report.findings}
    assert all(
        f.code != "too_long" or f.severity is ParseabilitySeverity.INFO
        for f in report.findings
    )


def test_flags_bullets_that_do_not_start_with_an_action_verb() -> None:
    """'Responsible for' reads as a duty, not an achievement."""
    passive = """
    Jane Doe
    jane@example.com

    Experience
    - Responsible for the deployment pipeline in 2021
    - Worked on various services
    - Helped with the migration

    Education
    BSc, 2016

    Skills
    Python
    """

    assert "weak_bullet_verbs" in codes(passive)


def test_does_not_flag_strong_bullets() -> None:
    """A CV already leading with action verbs is left alone."""
    assert "weak_bullet_verbs" not in codes(GOOD_CV)


def test_flags_bullets_without_numbers() -> None:
    """Achievements without scale are not credible."""
    vague = """
    Jane Doe
    jane@example.com

    Experience
    - Led the migration to a new platform in March 2021
    - Built a reporting service for the finance team
    - Improved the deployment process substantially

    Education
    BSc, 2016

    Skills
    Python
    """

    assert "unquantified_bullets" in codes(vague)


def test_findings_are_ordered_most_severe_first() -> None:
    """A UI can render the list as-is."""
    report = check_parseability("no contact details here at all")

    penalties = [f.severity.penalty for f in report.findings]
    assert penalties == sorted(penalties, reverse=True)


def test_score_never_goes_below_zero() -> None:
    """A comprehensively bad CV floors at zero rather than going negative."""
    report = check_parseability("x")

    assert report.score >= 0


def test_analysis_is_deterministic() -> None:
    """The same text always produces the same report."""
    assert check_parseability(GOOD_CV) == check_parseability(GOOD_CV)
