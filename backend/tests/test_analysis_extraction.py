from datetime import date

from cv_pal.analysis.extraction import extract_profile

# A two-column CV as pypdf actually extracts one: dates one word per line, the
# sidebar heading mid-job-list, reading order scrambled. Taken from a real file.
TWO_COLUMN_CV = """CV

Ada Lovelace
Senior

Software

Engineer

Lisbon,

Portugal

ada@example.com

linkedin.com/in/adalovelace
github.com/ada

EXPERIENCE
Northwind Digital, Lisbon — Senior Software Engineer
JUN
2021
-
Present
Built the payments service in Python and PostgreSQL.
SKILLS
Python, PostgreSQL, Docker, Kubernetes
Acme Systems, Porto — Backend Engineer
AUG
2018
-
FEB
2021
Maintained a Django monolith.
EDUCATION
University of Minho, Braga — BSc Computer Science
SEP
2014
-
JUL
2017
"""


# The ordinary case: one column, a name, a title, a place, then a labelled summary.
SINGLE_COLUMN_CV = """Curriculum Vitae

Ana Silva
Senior Backend Engineer
Lisbon, Portugal
ana@example.com | linkedin.com/in/anasilva

PROFILE
Backend engineer with nine years on payment systems. Comfortable owning a service
from schema to on-call rota.

EXPERIENCE
Northwind Digital, Lisbon — Senior Software Engineer
JUN 2021 - Present
Built the payments service in Python and PostgreSQL.
"""


def test_reads_the_headline_and_the_place_from_the_header() -> None:
    """The wizard asked users to type what the CV in front of it already said."""
    profile = extract_profile(SINGLE_COLUMN_CV)

    assert profile.headline == "Senior Backend Engineer"
    assert profile.location == "Lisbon, Portugal"


def test_reads_the_summary_from_whichever_heading_held_it() -> None:
    """A CV headed Profile means the same thing as one headed Summary."""
    profile = extract_profile(SINGLE_COLUMN_CV)

    assert profile.summary is not None
    assert profile.summary.startswith("Backend engineer with nine years")


def test_proposes_no_headline_when_the_header_did_not_survive_extraction() -> None:
    """A guess is only worth showing when the layout gave it something to read.

    The two-column file emits the title one word per line, so there is no headline in
    it to find — and inventing one from the fragments would be the fabrication this
    module exists to avoid.
    """
    profile = extract_profile(TWO_COLUMN_CV)

    assert profile.headline is None
    assert profile.summary is None


def test_reads_every_role_despite_a_sidebar_heading_mid_list() -> None:
    """A SKILLS heading between two jobs must not swallow the second one.

    This is the defect the real CV exposed: with entries assigned to whichever heading
    precedes them, a second-column sidebar heading lands mid-list and two roles vanish.
    """
    profile = extract_profile(TWO_COLUMN_CV)

    organisations = [e.organisation for e in profile.experiences]
    assert organisations == ["Northwind Digital", "Acme Systems"]


def test_separates_study_from_work_by_content() -> None:
    """The university entry is education even though no heading bounds it reliably."""
    profile = extract_profile(TWO_COLUMN_CV)

    assert [e.organisation for e in profile.educations] == ["University of Minho"]
    assert "University of Minho" not in [e.organisation for e in profile.experiences]


def test_rejoins_a_date_column_split_over_five_lines() -> None:
    """`AUG` / `2018` / `-` / `FEB` / `2021` is one date range, not five fragments."""
    profile = extract_profile(TWO_COLUMN_CV)
    acme = next(e for e in profile.experiences if e.organisation == "Acme Systems")

    assert acme.start_date == date(2018, 8, 1)
    assert acme.end_date == date(2021, 2, 1)


def test_an_open_ended_role_has_no_end_date() -> None:
    """A role ending in Present is current, stored as a null end date."""
    profile = extract_profile(TWO_COLUMN_CV)
    current = next(
        e for e in profile.experiences if e.organisation == "Northwind Digital"
    )

    assert current.start_date == date(2021, 6, 1)
    assert current.end_date is None


def test_splits_organisation_from_location() -> None:
    """The heading is `Organisation, Location - Title`."""
    profile = extract_profile(TWO_COLUMN_CV)
    first = profile.experiences[0]

    assert first.organisation == "Northwind Digital"
    assert first.location == "Lisbon"
    assert first.title == "Senior Software Engineer"


def test_contact_details_are_read_and_not_confused_with_each_other() -> None:
    """The email's domain is not the personal website."""
    contact = extract_profile(TWO_COLUMN_CV).contact

    assert contact.email == "ada@example.com"
    assert contact.linkedin_url == "linkedin.com/in/adalovelace"
    assert contact.website_url == "github.com/ada"
    assert contact.website_url != "example.com"


def test_only_recognised_skills_are_proposed() -> None:
    """A skills list is unstructured prose; proposing every fragment is unusable."""
    skills = extract_profile(TWO_COLUMN_CV).skills

    assert "python" in skills
    assert "postgresql" in skills
    assert "kubernetes" in skills


def test_an_unparseable_document_returns_an_empty_proposal() -> None:
    """Finding nothing is a normal outcome, not an error."""
    profile = extract_profile("A scanned image with no extractable structure at all.")

    assert profile.experiences == ()
    assert profile.educations == ()


def test_extraction_is_deterministic() -> None:
    """The same document always yields the same proposal."""
    assert extract_profile(TWO_COLUMN_CV) == extract_profile(TWO_COLUMN_CV)


# One column with the dates at the end of each heading line, several roles grouped under
# one employer, and both `Title, Employer` and `Employer · Title`. Every role in a CV
# laid out like this used to come back dateless, with its fields swapped.
DATES_ON_THE_HEADING_CV = """Sam Taylor
Platform Engineer
sam@example.com

EXPERIENCE
Globex Corporation, Leeds Mar 2012 – Present
Staff Engineer (Platform) Jan 2020 – Present
• Runs the deployment tooling.
Stack: Go, Terraform
Support Engineer (Tooling & Automation) Mar 2012 – Jan 2020
• Wrote the on-call runbooks.
QA Tester, Initech Labs Jun 2010 – Mar 2012
• Filed regressions found in 2010 – 2011.
Hooli, Cardiff · Warehouse Assistant (summer placement) Jul 2009 – Sep 2009
PROJECTS
• A chess engine, written in Rust.
EDUCATION
BSc Physics · University of Leeds · thesis on crystal growth 2006 – 2009
BTEC Engineering · Northfield College, Bristol 2004 – 2006
"""


def test_reads_dates_written_at_the_end_of_the_heading_line() -> None:
    """The range's own dash is not the separator between employer and title."""
    roles = extract_profile(DATES_ON_THE_HEADING_CV).experiences

    assert [(r.start_date, r.end_date) for r in roles] == [
        (date(2020, 1, 1), None),
        (date(2012, 3, 1), date(2020, 1, 1)),
        (date(2010, 6, 1), date(2012, 3, 1)),
        (date(2009, 7, 1), date(2009, 9, 1)),
    ]


def test_roles_grouped_under_an_employer_take_its_name() -> None:
    """The employer line is not a role of its own; the roles under it belong to it."""
    roles = extract_profile(DATES_ON_THE_HEADING_CV).experiences

    assert [(r.organisation, r.title) for r in roles[:2]] == [
        ("Globex Corporation", "Staff Engineer (Platform)"),
        ("Globex Corporation", "Support Engineer (Tooling & Automation)"),
    ]
    assert roles[0].location == "Leeds"


def test_tells_title_from_employer_by_what_the_words_say() -> None:
    """`Title, Employer` and `Employer, City · Title` both come out right."""
    roles = extract_profile(DATES_ON_THE_HEADING_CV).experiences

    assert (roles[2].organisation, roles[2].title) == ("Initech Labs", "QA Tester")
    assert (roles[3].organisation, roles[3].title, roles[3].location) == (
        "Hooli",
        "Warehouse Assistant (summer placement)",
        "Cardiff",
    )


def test_a_bullet_ending_in_a_date_range_is_not_a_heading() -> None:
    """A list item that happens to end in a date range belongs to the role above."""
    roles = extract_profile(DATES_ON_THE_HEADING_CV).experiences

    assert len(roles) == 4
    assert "regressions" in (roles[2].description or "")


def test_a_later_section_heading_ends_the_last_role() -> None:
    """Projects after the last job are not that job's description."""
    last = extract_profile(DATES_ON_THE_HEADING_CV).experiences[-1]

    assert "chess" not in (last.description or "")


def test_a_long_education_line_keeps_its_note_out_of_the_fields() -> None:
    """Qualification · Institution · note: the note is description, not the name."""
    courses = extract_profile(DATES_ON_THE_HEADING_CV).educations

    assert [(c.title, c.organisation) for c in courses] == [
        ("BSc Physics", "University of Leeds"),
        ("BTEC Engineering", "Northfield College"),
    ]
    assert courses[0].description == "thesis on crystal growth"
    assert courses[1].location == "Bristol"


def test_a_place_before_a_year_is_not_read_as_a_month() -> None:
    """`Bristol 2004 - 2006` starts in 2004, not in a month called Bristol."""
    course = extract_profile(DATES_ON_THE_HEADING_CV).educations[1]

    assert course.start_date == date(2004, 1, 1)
    assert course.end_date == date(2006, 12, 1)


# Title and employer on lines of their own, the dates below them — or above.
STACKED_CV = """EXPERIENCE
Software Engineer
Umbrella Ltd
03/2014 – 11/2016
• Shipped the billing service.
Jan 2017 – now
Staff Engineer at Initech
• Leads the platform team.
"""


def test_reads_a_heading_stacked_over_its_dates() -> None:
    """`Title` / `Employer` / `03/2014 - 11/2016`, numeric months included."""
    first = extract_profile(STACKED_CV).experiences[0]

    assert (first.title, first.organisation) == ("Software Engineer", "Umbrella Ltd")
    assert (first.start_date, first.end_date) == (date(2014, 3, 1), date(2016, 11, 1))


def test_reads_dates_written_above_the_heading() -> None:
    """Dates first, then `Title at Employer`."""
    second = extract_profile(STACKED_CV).experiences[1]

    assert (second.title, second.organisation) == ("Staff Engineer", "Initech")
    assert (second.start_date, second.end_date) == (date(2017, 1, 1), None)


def test_rejoins_a_heading_that_wrapped_onto_the_dates_line() -> None:
    """A narrow column wraps a long title onto the line that carries the dates."""
    text = """EXPERIENCE
Initech Labs, York — Principal Platform
Engineer (Infrastructure) MAR 2021 - PRESENT
Built things.
"""
    role = extract_profile(text).experiences[0]

    assert role.organisation == "Initech Labs"
    assert role.title == "Principal Platform Engineer (Infrastructure)"
    assert role.start_date == date(2021, 3, 1)
