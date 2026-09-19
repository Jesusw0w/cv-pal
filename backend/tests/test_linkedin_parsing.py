"""Parsing a LinkedIn profile, checked against the shape a real export actually has.

The fixture below reproduces the layout of a genuine "Save to PDF" export line for
line; the person, employers and schools in it are invented. Every assertion here failed
against the first implementation, which is the point of keeping it: the layout is not
the one a CV uses, and guessing at it from the documentation produced a parser that
looked right and read the wrong fields.

Keep the awkward parts when editing it — the accented characters, the two employers
sharing a name prefix, the three roles under one employer line, and the location that
appears with and without a region. Each of those is a bug this fixture caught.
"""

from datetime import date

from cv_pal.analysis.linkedin import (
    looks_like_linkedin,
    parse_profile,
    review,
)
from cv_pal.analysis.linkedin_export import parse_export
from cv_pal.constants import LinkedInSectionStatus, LinkedInSource
from tests.helpers import linkedin_archive

# Sidebar, then identity, then body; several roles share one employer line. The
# non-breaking spaces are real — pypdf emits them, and they caused a bug.
REAL_EXPORT = """\
Contact
+351900000000 (Mobile)
someone@example.com
www.linkedin.com/in/ines-marques-example
(LinkedIn)
Top Skills
Amazon S3
Version Control
Jira
Languages
Português (Native or Bilingual)
English (Full Professional)
Spanish (Limited Working)
Inês Marques
Senior Software Developer at Northgate Capital Markets
Lisbon, Lisbon, Portugal
Experience
Northgate Capital Markets
5 years 6 months
Senior Software Developer
June 2025 - Present (1 year 2 months)
Data Analyst
April 2023 - August 2025 (2 years 5 months)
Lisbon, Portugal
Senior Risk Analyst
February 2021 - March 2023 (2 years 2 months)
Lisbon, Portugal
Northgate Securities Services
Risk Analyst
May 2019 - January 2021 (1 year 9 months)
Lisbon, Lisbon, Portugal
Vantis Automotive
Accounts Receivables
August 2018 - January 2019 (6 months)
Education
Atlântico Business School
Master's degree, Finance · (2016 - 2018)
Universidade de Alvorada
Computer Engineering · (2017 - 2018)
Universidade Atlântica - Viseu
Bachelor's degree, Management · (2013 - 2016)
  Page 1 of 1
"""


def test_a_profile_export_is_recognised() -> None:
    """The document is detected without the user having to say what it is."""
    assert looks_like_linkedin(REAL_EXPORT) is True


def test_an_ordinary_cv_is_not_mistaken_for_a_profile() -> None:
    """Merely listing a LinkedIn address does not make a CV a profile export."""
    cv = "Jane Doe\nSoftware Engineer\nSkills: Python, Go\nReferences on request."
    assert looks_like_linkedin(cv) is False


def test_identity_is_read_from_after_the_sidebar() -> None:
    """The name and headline follow the sidebar, not the top of the document.

    Reading the preamble — which is what a CV parser would do — found neither.
    """
    snapshot = parse_profile(REAL_EXPORT, source=LinkedInSource.PDF)

    assert snapshot.name == "Inês Marques"
    assert snapshot.headline == "Senior Software Developer at Northgate Capital Markets"
    assert snapshot.profile_url == "https://www.linkedin.com/in/ines-marques-example"


def test_several_roles_at_one_employer_all_carry_that_employer() -> None:
    """The employer is named once and carried forward across its roles.

    Taking a fixed two lines back instead picked up the tenure line ("5 years 6
    months") and the previous role's location as employers.
    """
    snapshot = parse_profile(REAL_EXPORT, source=LinkedInSource.PDF)
    roles = [(p.organisation, p.title) for p in snapshot.positions]

    assert roles == [
        ("Northgate Capital Markets", "Senior Software Developer"),
        ("Northgate Capital Markets", "Data Analyst"),
        ("Northgate Capital Markets", "Senior Risk Analyst"),
        ("Northgate Securities Services", "Risk Analyst"),
        ("Vantis Automotive", "Accounts Receivables"),
    ]


def test_role_dates_and_locations_survive() -> None:
    """Dates parse, and a location attaches to the role above rather than the next."""
    snapshot = parse_profile(REAL_EXPORT, source=LinkedInSource.PDF)
    current, second = snapshot.positions[0], snapshot.positions[1]

    assert current.start_date == date(2025, 6, 1)
    assert current.end_date is None  # "Present"
    assert second.end_date == date(2025, 8, 1)
    assert second.location == "Lisbon, Portugal"


def test_education_takes_the_qualification_from_the_date_line() -> None:
    """Education puts the degree and the dates on one line, the school above it."""
    snapshot = parse_profile(REAL_EXPORT, source=LinkedInSource.PDF)
    entries = [(e.organisation, e.title) for e in snapshot.educations]

    assert entries == [
        ("Atlântico Business School", "Master's degree, Finance"),
        ("Universidade de Alvorada", "Computer Engineering"),
        (
            "Universidade Atlântica - Viseu",
            "Bachelor's degree, Management",
        ),
    ]


def test_the_pdf_carries_only_the_top_three_skills() -> None:
    """What the PDF route actually gives you, pinned so the limitation stays visible.

    LinkedIn's own PDF exports the *Top Skills* block, not the skill list. This is the
    reason the data export exists as a route and why a later PDF import must not be
    allowed to overwrite one.
    """
    snapshot = parse_profile(REAL_EXPORT, source=LinkedInSource.PDF)

    assert snapshot.skills == ("Amazon S3", "Version Control", "Jira")
    # And no About section and no role descriptions come through at all.
    assert snapshot.about is None
    assert all(position.description is None for position in snapshot.positions)


def test_review_flags_the_thin_profile_the_pdf_describes() -> None:
    """The review says what a recruiter would notice about this profile."""
    snapshot = parse_profile(REAL_EXPORT, source=LinkedInSource.PDF)

    result = review(snapshot, experiences=[], target_roles=[])
    by_section = {section.section: section.status for section in result.sections}

    assert by_section["about"] is LinkedInSectionStatus.MISSING
    assert by_section["skills"] is LinkedInSectionStatus.THIN
    assert by_section["experience"] is LinkedInSectionStatus.OK
    assert result.score < 100
    # No target roles set, so there is nothing to measure search coverage against.
    assert result.coverage is None


def test_paste_is_not_scored_for_sections_it_could_not_delimit() -> None:
    """A paste reports what it found and says what it could not judge."""
    snapshot = parse_profile(REAL_EXPORT, source=LinkedInSource.PASTE)

    result = review(snapshot, experiences=[], target_roles=[])

    assert all(
        section.status is not LinkedInSectionStatus.MISSING
        for section in result.sections
    )
    assert "no section boundaries" in result.note


def test_the_data_export_carries_what_the_pdf_drops() -> None:
    """The archive states the full skill list, the About text and role descriptions."""
    data = linkedin_archive(
        {
            "Profile.csv": (
                "First Name,Last Name,Headline,Summary\n"
                "Inês,Marques,Senior Software Developer,"
                '"Fifteen years building risk systems."\n'
            ),
            "Positions.csv": (
                "Company Name,Title,Description,Location,Started On,Finished On\n"
                "Northgate Capital Markets,Senior Software Developer,"
                '"Led the migration to event sourcing.",'
                "Lisbon,Jun 2025,\n"
            ),
            "Skills.csv": (
                "Name\nPython\nFastAPI\nAngular\nAmazon S3\nJira\nTerraform\n"
            ),
            "Education.csv": (
                "School Name,Degree Name,Field Of Study,Start Date,End Date\n"
                "Atlântico Business School,Master's degree,Finance,2016,2018\n"
            ),
        }
    )

    snapshot = parse_export(data)

    assert snapshot.headline == "Senior Software Developer"
    assert snapshot.about == "Fifteen years building risk systems."
    assert len(snapshot.skills) == 6  # against three from the PDF
    assert snapshot.positions[0].description == "Led the migration to event sourcing."
    assert snapshot.positions[0].start_date == date(2025, 6, 1)
    assert snapshot.positions[0].end_date is None
    assert snapshot.educations[0].title == "Master's degree Finance"


def test_an_archive_without_profile_files_parses_to_nothing() -> None:
    """Selecting the wrong files when requesting the export is reported, not crashed."""
    snapshot = parse_export(linkedin_archive({"Connections.csv": "First Name\nAda\n"}))

    assert snapshot.is_empty is True


def test_a_file_that_is_not_a_zip_is_refused() -> None:
    """A non-archive is a parse failure rather than an exception the caller sees."""
    try:
        parse_export(b"not a zip at all")
    except ValueError:
        return
    raise AssertionError("expected a ValueError")


def test_consistency_reports_both_directions() -> None:
    """Employers on one record and not the other are both surfaced."""
    from cv_pal.analysis.extraction import ExtractedEntry

    snapshot = parse_profile(REAL_EXPORT, source=LinkedInSource.PDF)
    profile_only = ExtractedEntry(
        organisation="Some Other Employer",
        title="Engineer",
        start_date=date(2015, 1, 1),
        end_date=date(2018, 1, 1),
    )

    result = review(snapshot, experiences=[profile_only], target_roles=[])
    kinds = {issue.kind.value for issue in result.consistency}

    assert "employer_only_on_linkedin" in kinds
    assert "employer_only_on_profile" in kinds
