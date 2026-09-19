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
