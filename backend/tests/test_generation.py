"""Phase 8, first slice: a CV rendered for one posting from the profile alone.

The centre of this file is `test_nothing_is_written_that_the_profile_does_not_say`. The
feature's whole claim is that it cannot invent experience, and that test is what makes
the claim enforceable rather than aspirational — it fails the moment anything starts
composing prose about the user.
"""

import io
from dataclasses import replace
from datetime import date

from docx import Document
from httpx import AsyncClient
from pypdf import PdfReader

from cv_pal.analysis.parseability import check_parseability
from cv_pal.generation.docx_export import render_docx
from cv_pal.generation.pdf_export import render_pdf
from cv_pal.generation.tailored_cv import (
    EducationFact,
    ExperienceFact,
    ProfileFacts,
    SkillFact,
    content_values,
    tailor,
)
from tests.helpers import register_and_login

POSTING = (
    "Senior Backend Engineer. Requirements: strong Python and PostgreSQL experience, "
    "and Docker in production. Nice to have: Kubernetes and Terraform. This role is "
    "fully remote."
)

BACKEND = ExperienceFact(
    id=1,
    title="Backend Engineer",
    organisation="Acme",
    start_date=date(2021, 3, 1),
    end_date=date(2024, 6, 1),
    location="Lisbon, Portugal",
    description="Built and ran the billing service.",
)
SUPPORT = ExperienceFact(
    id=2,
    title="Support Engineer",
    organisation="Northwind",
    start_date=date(2019, 1, 1),
    end_date=date(2021, 2, 1),
    description="Handled escalations for the payments platform.",
)


def facts(*skills: SkillFact) -> ProfileFacts:
    """A profile with two roles, one qualification, and the skills given."""
    return ProfileFacts(
        full_name="Ada Rivera",
        email="ada@example.com",
        headline="Backend engineer, payments and billing",
        summary="Ten years building transactional systems.",
        location="Lisbon, Portugal",
        linkedin_url="https://www.linkedin.com/in/ada",
        experiences=(BACKEND, SUPPORT),
        educations=(
            EducationFact(
                institution="University of Lisbon",
                qualification="BSc Computer Science",
                start_date=date(2014, 9, 1),
                end_date=date(2018, 6, 1),
            ),
        ),
        skills=skills,
    )


def skill(name: str, canonical_name: str, *evidenced_by: int) -> SkillFact:
    """A skill, evidenced by the roles given."""
    return SkillFact(
        name=name,
        canonical_name=canonical_name,
        evidenced_by=frozenset(evidenced_by),
    )


# --- The invariant the whole feature rests on ---


def test_nothing_is_written_that_the_profile_does_not_say() -> None:
    """Every content value in the document is copied from a profile row.

    This is *never fabricate experience*, as a test rather than as a principle. The
    document's own structure — headings, separators, the "Relevant here" label — is
    fixed text this module authors; everything else must be the user's.

    If a future change starts generating a summary, rewriting a bullet, or borrowing a
    phrase from the posting, this fails. That is the point: the three permitted
    transforms allow exactly one of those, and it is not implemented here.
    """
    profile = facts(
        skill("Python", "python", 1),
        skill("PostgreSQL", "postgresql", 1),
        skill("Docker", "docker", 1, 2),
    )

    document = tailor(profile, POSTING).markdown

    allowed = content_values(profile)
    structural = {
        "#",
        "##",
        "###",
        "|",
        "-",
        "Summary",
        "Skills",
        "Experience",
        "Education",
        "Relevant",
        "here:",
        "Present",
    }
    # Compare on whole lines, stripped of the structure, so a smuggled sentence cannot
    # hide inside an otherwise-legitimate line.
    for line in document.splitlines():
        text = line.lstrip("#").strip()
        if not text or text in structural:
            continue
        for part in text.split(" | "):
            part = part.removeprefix("Relevant here: ").strip()
            if not part or _is_date_span(part):
                continue
            assert _is_grounded(part, allowed), f"ungrounded: {part!r}"


def _is_date_span(text: str) -> bool:
    """Report whether a fragment is a rendered date range rather than content."""
    return all(
        piece.isdigit() or piece in {"-", "Present"} or len(piece) == 3
        for piece in text.replace("-", " - ").split()
    )


def _is_grounded(text: str, allowed: set[str]) -> bool:
    """Report whether a fragment is a profile value, or a list of them.

    Args:
        text: A rendered fragment.
        allowed: Every value the profile carries.

    Returns:
        True when the fragment is one profile value, or a comma- or comma-and-heading
        joined list of them — the only two shapes the renderer produces.
    """
    if text in allowed:
        return True
    pieces = [piece.strip() for piece in text.replace(",", "\n").split("\n")]
    return all(piece in allowed for piece in pieces if piece)


# --- Surfacing ---


def test_the_posting_decides_which_skills_come_first() -> None:
    """Ordering is the transform. Nothing is added; what is relevant is made visible."""
    profile = facts(
        skill("Accessibility", "accessibility", 1),
        skill("Python", "python", 1),
        skill("Zsh", "zsh", 2),
        skill("PostgreSQL", "postgresql", 1),
    )

    result = tailor(profile, POSTING)
    listed = result.markdown.split("## Skills")[1].split("##")[0].strip()

    assert listed.startswith(("Python", "PostgreSQL"))
    assert {item.skill for item in result.surfaced} == {"Python", "PostgreSQL"}


def test_a_surfaced_skill_names_the_roles_that_back_it() -> None:
    """The rationale the spec wants per change: which fact, and what evidences it."""
    profile = facts(skill("Docker", "docker", 1, 2))

    surfaced = tailor(profile, POSTING).surfaced

    assert len(surfaced) == 1
    assert surfaced[0].skill == "Docker"
    assert surfaced[0].required is True
    assert surfaced[0].evidence == (
        "Backend Engineer, Acme",
        "Support Engineer, Northwind",
    )


def test_each_role_shows_only_the_skills_that_role_evidences() -> None:
    """Surfacing is per role, from `SkillEvidence` — not the whole skill list repeated.

    A role claiming every term the posting used would be keyword stuffing, and it would
    also be false: the join exists precisely to say which role demonstrated what.
    """
    profile = facts(
        skill("Python", "python", 1),
        skill("Kubernetes", "kubernetes", 2),
    )

    document = tailor(profile, POSTING).markdown
    # Only the role blocks: both skills legitimately appear in the Skills section, so
    # slicing from the Experience heading is what makes this test about surfacing.
    roles = document.split("## Experience")[1]
    backend, support = roles.split("### Support Engineer")

    assert "Relevant here: Python" in backend
    assert "Kubernetes" not in backend
    assert "Relevant here: Kubernetes" in support


def test_an_unevidenced_skill_is_left_out_and_reported() -> None:
    """A skill no role demonstrates is a claim, not a fact.

    Dropping it silently would be its own kind of dishonesty — towards the user, who
    cannot see why their CV is missing something they entered — so it is named.
    """
    profile = facts(skill("Python", "python", 1), skill("Rust", "rust"))

    result = tailor(profile, POSTING)

    assert "Rust" not in result.markdown
    assert result.omitted_unevidenced == ("Rust",)


def test_a_requirement_with_no_evidence_is_a_gap_and_never_text() -> None:
    """The permitted transforms' boundary: unreachable terms are named, never written.

    This is the check that separates tailoring from keyword stuffing. A posting asking
    for Kubernetes does not put Kubernetes on a CV that cannot evidence it.
    """
    profile = facts(skill("Python", "python", 1))

    result = tailor(profile, POSTING)

    assert "kubernetes" not in result.markdown.casefold()
    assert "kubernetes" in {gap.term for gap in result.gaps}
    assert any(gap.required and gap.term == "postgresql" for gap in result.gaps)


def test_the_same_profile_and_posting_always_produce_the_same_document() -> None:
    """Deterministic, per principle 1 — which is what makes storing it unnecessary."""
    profile = facts(skill("Python", "python", 1), skill("Docker", "docker", 2))

    assert tailor(profile, POSTING).markdown == tailor(profile, POSTING).markdown


# --- The document has to survive the checks this project applies to uploads ---


def test_the_generated_cv_passes_our_own_parseability_check() -> None:
    """Generating what we would flag on upload would be the sharpest inconsistency.

    The headings are the literal words `EXPECTED_SECTIONS` looks for and the dates are
    in a form `parseability` names as machine-readable, so this is a real coupling
    rather than a coincidence worth pinning.
    """
    profile = facts(skill("Python", "python", 1), skill("Docker", "docker", 2))

    report = check_parseability(tailor(profile, POSTING).markdown)

    assert report.blocking == ()
    assert not [f for f in report.findings if f.code.startswith("missing_section_")]
    assert "no_parseable_dates" not in {f.code for f in report.findings}
    assert "no_email" not in {f.code for f in report.findings}


def test_a_phone_number_reaches_the_contact_line() -> None:
    """A CV we generate has to be able to carry what our own ATS check asks for.

    Until the profile grew the field, every document this generated drew the `no_phone`
    finding that the same product reports about uploads.
    """
    profile = replace(facts(), phone="+351 912 345 678")

    result = tailor(profile, POSTING)

    assert "+351 912 345 678" in result.markdown
    assert "no_phone" not in {
        f.code for f in check_parseability(result.markdown).findings
    }


def test_a_current_role_reads_as_present_rather_than_undated() -> None:
    """A missing end date means ongoing; leaving it blank would look like bad data."""
    profile = ProfileFacts(
        full_name="Ada Rivera",
        email="ada@example.com",
        experiences=(
            ExperienceFact(
                id=1,
                title="Staff Engineer",
                organisation="Acme",
                start_date=date(2024, 7, 1),
                end_date=None,
            ),
        ),
    )

    assert "Jul 2024 - Present" in tailor(profile, POSTING).markdown


def test_an_empty_profile_produces_a_document_rather_than_a_crash() -> None:
    """A new account can press the button. What comes back is empty, and honest."""
    result = tailor(ProfileFacts(full_name=None, email="new@example.com"), POSTING)

    assert "## Experience" not in result.markdown
    assert result.surfaced == ()
    assert any(gap.required for gap in result.gaps)


# --- Through the API ---


async def test_tailoring_a_posting_returns_the_document_and_its_reasoning(
    client: AsyncClient,
) -> None:
    """End to end: profile, posting, and the explanation that travels with the CV."""
    headers = await register_and_login(client)

    experience = await client.post(
        "/profile/experiences",
        headers=headers,
        json={
            "organisation": "Acme",
            "title": "Backend Engineer",
            "start_date": "2021-03-01",
            "end_date": "2024-06-01",
        },
    )
    experience_id = experience.json()["id"]
    await client.post(
        "/profile/skills",
        headers=headers,
        json={"name": "Python", "evidence_experience_ids": [experience_id]},
    )
    posting = await client.post(
        "/jobs/paste",
        headers=headers,
        json={"title": "Senior Backend Engineer", "description": POSTING},
    )
    posting_id = posting.json()["id"]

    response = await client.post(f"/jobs/{posting_id}/tailor", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert "Backend Engineer, Acme" in body["markdown"]
    assert [item["skill"] for item in body["surfaced"]] == ["Python"]
    assert "kubernetes" in {gap["term"] for gap in body["gaps"]}
    assert body["parseability"]["score"] > 0


async def test_tailoring_another_users_posting_is_a_404(client: AsyncClient) -> None:
    """Ownership is resolved through the posting, so it simply does not exist."""
    owner = await register_and_login(client, email="owner@example.com")
    posting = await client.post(
        "/jobs/paste",
        headers=owner,
        json={"title": "Senior Backend Engineer", "description": POSTING},
    )
    intruder = await register_and_login(client, email="intruder@example.com")

    response = await client.post(
        f"/jobs/{posting.json()['id']}/tailor", headers=intruder
    )

    assert response.status_code == 404


async def test_tailoring_requires_authentication(client: AsyncClient) -> None:
    """A CV is built from personal data, so none of this is anonymous."""
    assert (await client.post("/jobs/1/tailor")).status_code == 401


def test_the_employers_own_name_is_not_reported_as_a_missing_skill() -> None:
    """A posting repeats its employer throughout, and `A.Team` looks like a technology.

    The extractor cannot tell the difference; the caller can, because the company is a
    stored field. Reporting the employer as a skill the user lacks is both wrong and
    slightly absurd.
    """
    posting = (
        "A.Team is hiring. Requirements: Python. At A.Team you will join a network of "
        "builders. A.Team works with high-growth companies."
    )
    profile = facts(skill("Python", "python", 1))

    with_company = tailor(profile, posting, company="A.Team")
    without = tailor(profile, posting)

    assert "a.team" not in {gap.term for gap in with_company.gaps}
    assert "a.team" in {gap.term for gap in without.gaps}


def test_recruiting_prose_is_not_reported_as_a_gap() -> None:
    """A gap list is meant to be acted on, and "you are missing: built" is not.

    Found by reading real output rather than a fixture: an A.Team posting produced
    `building`, `built`, `builders` and `companies` as required gaps. Same defect class
    as session 18's `hiring` / `engineer` / `experience`.
    """
    posting = (
        "We are building the future. Requirements: Python. You will join a team of "
        "builders who have built products for companies. Engineering is our mission."
    )

    gaps = {
        gap.term for gap in tailor(facts(skill("Python", "python", 1)), posting).gaps
    }

    assert not gaps & {"building", "built", "builders", "companies", "engineering"}


def test_the_gap_list_is_capped_so_it_can_be_acted_on() -> None:
    """Ranked required-first, then by emphasis, and cut — not a wall of forty terms."""
    posting = "Requirements: " + ", ".join(f"tech{index}" for index in range(40))

    gaps = tailor(facts(), posting).gaps

    assert len(gaps) <= 12


# --- Transform 2: substitute within an equivalence class ---


def test_the_postings_spelling_is_adopted_when_the_alias_map_says_it_may() -> None:
    """`Postgres` becomes `PostgreSQL` because the map asserts they are one thing."""
    profile = facts(skill("Postgres", "postgresql", 1))

    result = tailor(profile, POSTING)

    assert "PostgreSQL" in result.markdown
    assert "Postgres," not in result.markdown
    assert result.substitutions[0].from_term == "Postgres"
    assert result.substitutions[0].to_term == "PostgreSQL"


def test_substitution_never_crosses_an_equivalence_class() -> None:
    """A posting asking for Oracle does not turn Postgres experience into Oracle.

    The clearest way this transform could become a lie, and the one PLANNING calls out
    by name.
    """
    profile = facts(skill("Postgres", "postgresql", 1))

    result = tailor(profile, "Requirements: Oracle database experience.")

    assert "Oracle" not in result.markdown
    assert result.substitutions == ()


def test_substitution_is_disabled_where_the_alias_map_asserts_nothing() -> None:
    """PLANNING requires transform 2 off outside software, and this is how it is off.

    No occupation detector, and no special case: the gate is "did `SKILL_ALIASES` put
    these two spellings together", and outside software it never has. A nursing profile
    gets its own words back because the map has no opinion about them, which is the
    same reason it must not guess.
    """
    profile = facts(skill("Phlebotomy", "phlebotomy", 1))

    result = tailor(profile, "Requirements: PHLEBOTOMY certification and IV therapy.")

    assert "Phlebotomy" in result.markdown
    assert "PHLEBOTOMY" not in result.markdown
    assert result.substitutions == ()


def test_a_substituted_word_is_reported_so_it_can_be_checked() -> None:
    """It is the only text in the document that is not literally the user's own."""
    profile = facts(skill("K8s", "kubernetes", 1), skill("Python", "python", 1))

    result = tailor(profile, "Requirements: Kubernetes and Python.")

    assert [(s.from_term, s.to_term) for s in result.substitutions] == [
        ("K8s", "Kubernetes")
    ]


# --- The .docx, which is the format an ATS actually ingests ---


def test_the_docx_carries_the_same_text_as_the_markdown() -> None:
    """Two renderers, one document model — so they cannot drift.

    Building Markdown and parsing it back to make a DOCX would turn the Markdown into a
    private interchange format, and a formatting change in one output would silently
    break the other.
    """
    profile = facts(skill("Python", "python", 1), skill("Docker", "docker", 1))
    result = tailor(profile, POSTING)

    document = Document(io.BytesIO(render_docx(result.blocks)))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)

    for block in result.blocks:
        assert block.text in text


def test_the_docx_uses_real_heading_styles_rather_than_bold_text() -> None:
    """A parser reads the style name. Visually-bold body text carries no signal at all.

    This is the difference between an ATS finding an Experience section and finding an
    undifferentiated wall of paragraphs.
    """
    profile = facts(skill("Python", "python", 1))

    document = Document(io.BytesIO(render_docx(tailor(profile, POSTING).blocks)))
    styled = {
        paragraph.text: paragraph.style.name
        for paragraph in document.paragraphs
        # `style` is optional in python-docx's typing; a paragraph without one is not a
        # heading, which is exactly what this filter is deciding.
        if paragraph.style is not None
        and paragraph.style.name is not None
        and paragraph.style.name.startswith(("Title", "Heading"))
    }

    assert styled.get("Experience", "").startswith("Heading")
    assert styled.get("Skills", "").startswith("Heading")
    assert "Backend Engineer, Acme" in styled


def test_the_docx_puts_nothing_in_a_header_or_a_table() -> None:
    """Both are how a parser loses your email address.

    Contact details in a page header are the classic disappearance: many parsers read
    the body story only.
    """
    profile = facts(skill("Python", "python", 1))

    document = Document(io.BytesIO(render_docx(tailor(profile, POSTING).blocks)))

    assert document.tables == []
    for section in document.sections:
        assert all(not p.text.strip() for p in section.header.paragraphs)
        assert all(not p.text.strip() for p in section.footer.paragraphs)
    body = "\n".join(p.text for p in document.paragraphs)
    assert "ada@example.com" in body


async def test_the_docx_download_is_named_and_typed(client: AsyncClient) -> None:
    """It has to arrive as a file, with a name that says which job it is for."""
    headers = await register_and_login(client)
    posting = await client.post(
        "/jobs/paste",
        headers=headers,
        json={
            "title": "Senior Backend Engineer",
            "company": "Acme",
            "description": POSTING,
        },
    )

    response = await client.post(
        f"/jobs/{posting.json()['id']}/tailor/docx", headers=headers
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="CV - Acme - Senior Backend Engineer.docx"'
    )
    # A real DOCX is a ZIP container, which is the same check uploads get.
    assert response.content.startswith(b"PK\x03\x04")


async def test_a_hostile_company_name_cannot_reshape_the_download_header(
    client: AsyncClient,
) -> None:
    """Company and title come from a third-party board and end up in a header.

    A quote or a newline there is header injection; a slash is a path the browser may
    interpret. The filename is rebuilt from an allowlist rather than cleaned, so this
    pins that it stays rebuilt.
    """
    headers = await register_and_login(client)
    posting = await client.post(
        "/jobs/paste",
        headers=headers,
        json={
            "title": '../../etc/passwd"',
            "company": 'Evil"\r\nX-Injected: yes',
            "description": POSTING,
        },
    )

    response = await client.post(
        f"/jobs/{posting.json()['id']}/tailor/docx", headers=headers
    )

    disposition = response.headers["content-disposition"]
    assert "x-injected" not in {key.lower() for key in response.headers}
    assert '"' not in disposition.removeprefix('attachment; filename="').removesuffix(
        '"'
    )
    assert "/" not in disposition
    assert "\n" not in disposition


# --- The PDF, which is what a human opens ---


def pdf_text(blocks: object) -> str:
    """Extract a generated PDF's text with the same reader the app uses on uploads."""
    reader = PdfReader(io.BytesIO(render_pdf(blocks)))  # type: ignore[arg-type]
    return "\n".join(page.extract_text() for page in reader.pages)


def test_the_pdf_is_a_real_pdf_carrying_real_text() -> None:
    """A PDF of images is the failure mode `parseability` calls out first.

    Read back with `pypdf` — the same reader that parses uploads — so this asserts the
    output survives the exact code path a user's own file would take.
    """
    profile = facts(skill("Python", "python", 1), skill("Docker", "docker", 1))
    result = tailor(profile, POSTING)

    assert render_pdf(result.blocks).startswith(b"%PDF-")

    text = pdf_text(result.blocks)
    for block in result.blocks:
        assert block.text in text


def test_the_generated_pdf_passes_our_own_parseability_check() -> None:
    """The strongest coupling available: our reader, then our checker, on our output.

    If the PDF renderer ever stops producing extractable single-column text, this fails
    rather than a user discovering it after an application disappears.
    """
    profile = facts(skill("Python", "python", 1), skill("Docker", "docker", 1))

    report = check_parseability(pdf_text(tailor(profile, POSTING).blocks))

    assert report.blocking == ()
    assert "no_email" not in {f.code for f in report.findings}
    assert "no_parseable_dates" not in {f.code for f in report.findings}
    assert not [f for f in report.findings if f.code.startswith("missing_section_")]


def test_markup_characters_in_a_profile_do_not_break_the_pdf() -> None:
    """ReportLab parses paragraph text as a small HTML dialect.

    A profile saying `C++ & <legacy>` either renders wrongly or raises mid-build, and
    every string here is user-supplied — the case where "probably fine" is wrong.
    """
    profile = ProfileFacts(
        full_name="Ada <Rivera> & Co",
        email="ada@example.com",
        summary="Built C++ & <legacy> billing systems.",
        experiences=(BACKEND,),
        skills=(skill("C++", "c++", 1),),
    )

    text = pdf_text(tailor(profile, "Requirements: C++ and billing experience.").blocks)

    assert "Built C++ & <legacy> billing systems." in text
    assert "Ada <Rivera> & Co" in text


async def test_the_pdf_download_is_named_and_typed(client: AsyncClient) -> None:
    """Same filename discipline as the DOCX: the parts come from a foreign board."""
    headers = await register_and_login(client)
    posting = await client.post(
        "/jobs/paste",
        headers=headers,
        json={
            "title": "Senior Backend Engineer",
            "company": "Acme",
            "description": POSTING,
        },
    )

    response = await client.post(
        f"/jobs/{posting.json()['id']}/tailor/pdf", headers=headers
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="CV - Acme - Senior Backend Engineer.pdf"'
    )
    assert response.content.startswith(b"%PDF-")
