"""Cover letters, and the check that keeps them honest.

The generator and `analysis.similarity` landed together on purpose. A deterministic
scaffold produces letters that resemble each other, which is precisely what the
self-similarity check exists to surface — shipping one without the other would be the
product doing the thing PLANNING says it exists to prevent.
"""

from httpx import AsyncClient

from cv_pal.analysis.similarity import jaccard, self_similarity, shingles
from tests.helpers import register_and_login

POSTING = (
    "Senior Backend Engineer at Acme. Requirements: strong Python and PostgreSQL "
    "experience, and Docker in production. Nice to have: Kubernetes."
)
OTHER_POSTING = (
    "Staff Platform Engineer at Northwind. Requirements: Terraform, Go and AWS. "
    "You will own the deployment pipeline end to end."
)


async def setup_profile(client: AsyncClient, headers: dict[str, str]) -> None:
    """Give the account one role and one evidenced skill."""
    await client.patch(
        "/profile",
        headers=headers,
        json={"summary": "Six years building transactional systems."},
    )
    experience = await client.post(
        "/profile/experiences",
        headers=headers,
        json={
            "organisation": "Acme",
            "title": "Backend Engineer",
            "start_date": "2021-03-01",
            "end_date": None,
        },
    )
    await client.post(
        "/profile/skills",
        headers=headers,
        json={"name": "Python", "evidence_experience_ids": [experience.json()["id"]]},
    )


async def save_posting(
    client: AsyncClient, headers: dict[str, str], description: str, title: str
) -> int:
    """Save a posting and return its id."""
    response = await client.post(
        "/jobs/paste",
        headers=headers,
        json={"title": title, "company": "Acme", "description": description},
    )
    posting_id: int = response.json()["id"]
    return posting_id


# --- The measure itself ---


def test_a_document_is_not_similar_to_nothing() -> None:
    """A first letter has nothing to repeat, and scoring it 100 would be nonsense."""
    assert self_similarity("Dear Hiring Team, I would like to apply.", []).score == 0


def test_two_empty_documents_are_not_identical() -> None:
    """Identical emptiness is not a similarity anyone wants reported."""
    assert jaccard(shingles(""), shingles("")) == 0.0


def test_the_same_letter_twice_scores_full_marks() -> None:
    """The signal the check exists for: this is the letter you already sent."""
    letter = "Dear Hiring Team, I am writing to apply for the role of Engineer at Acme."

    assert self_similarity(letter, [letter]).score == 100


def test_a_genuinely_different_letter_scores_low() -> None:
    """Otherwise the check would fire on every letter and be ignored within a week."""
    first = "Dear Hiring Team, I am writing to apply for the role of Engineer at Acme."
    second = (
        "I read your posting about the payments rewrite and wanted to write. Last "
        "winter I moved a billing system off a monolith under similar constraints."
    )

    assert self_similarity(second, [first]).score < 20


def test_the_closest_of_several_is_the_one_reported() -> None:
    """Naming which letter it repeats is what makes the number actionable."""
    target = "The deployment pipeline I built at Northwind ran two hundred times a day."
    previous = ["Something entirely unrelated about design systems.", target]

    result = self_similarity(target, previous)

    assert result.score == 100
    assert result.closest == 1


def test_a_lightly_edited_letter_still_reads_as_a_repeat() -> None:
    """Changing the company name is the edit people actually make.

    If that were enough to clear the check, the check would be theatre.
    """
    first = (
        "Dear Hiring Team, I am writing to apply for the role of Backend Engineer at "
        "Acme. I have six years of experience building transactional systems."
    )
    second = first.replace("Acme", "Northwind")

    # Measured at 62 with five-word shingles, against a warn line of 40.
    assert self_similarity(second, [first]).score > 50


# --- The letter ---


async def test_the_draft_is_assembled_from_profile_facts(client: AsyncClient) -> None:
    """Every claim about the user is theirs; the rest is the posting's or structure."""
    headers = await register_and_login(client)
    await setup_profile(client, headers)
    posting_id = await save_posting(client, headers, POSTING, "Senior Backend Engineer")

    response = await client.post(f"/jobs/{posting_id}/cover-letter", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert "Six years building transactional systems." in body["body"]
    assert "Senior Backend Engineer at Acme" in body["body"]
    # The evidence line names the role behind the claim, exactly as the CV does.
    assert body["evidence"] == ["- Python: Backend Engineer, Acme"]


async def test_the_draft_admits_the_part_it_cannot_write(client: AsyncClient) -> None:
    """The honest failure mode: a correct skeleton, and a note saying what is missing.

    Generating confident filler and letting the user discover in an interview that they
    cannot defend a sentence they never wrote is the alternative.
    """
    headers = await register_and_login(client)
    await setup_profile(client, headers)
    posting_id = await save_posting(client, headers, POSTING, "Senior Backend Engineer")

    body = (
        await client.post(f"/jobs/{posting_id}/cover-letter", headers=headers)
    ).json()

    assert body["needs_writing"] is True
    assert "[Write one paragraph here" in body["body"]


async def test_a_first_letter_has_nothing_to_repeat(client: AsyncClient) -> None:
    """Similarity is measured against kept letters, and there are none yet."""
    headers = await register_and_login(client)
    await setup_profile(client, headers)
    posting_id = await save_posting(client, headers, POSTING, "Senior Backend Engineer")

    body = (
        await client.post(f"/jobs/{posting_id}/cover-letter", headers=headers)
    ).json()

    assert body["similarity"] == 0
    assert body["similarity_warning"] is False


async def test_the_second_scaffolded_letter_is_flagged_as_a_repeat(
    client: AsyncClient,
) -> None:
    """The check earning its place.

    A deterministic scaffold produces near-identical letters, and the number says so
    rather than the product pretending otherwise. That message — *this is boilerplate,
    make it specific* — is the correct one, and it is why the check shipped with the
    generator instead of after it.
    """
    headers = await register_and_login(client)
    await setup_profile(client, headers)
    first = await save_posting(client, headers, POSTING, "Senior Backend Engineer")
    second = await save_posting(
        client, headers, OTHER_POSTING, "Staff Platform Engineer"
    )

    kept = (await client.post(f"/jobs/{first}/cover-letter", headers=headers)).json()
    await client.put(
        f"/jobs/{first}/cover-letter", headers=headers, json={"body": kept["body"]}
    )

    body = (await client.post(f"/jobs/{second}/cover-letter", headers=headers)).json()

    # Measured at 57-64 for two scaffolded letters aimed at different jobs.
    assert body["similarity"] > 50
    assert body["similarity_warning"] is True


async def test_writing_something_specific_lowers_the_score(client: AsyncClient) -> None:
    """The loop working. Nothing else lowers it, and nothing is shaped to.

    PLANNING's rule: the system never optimises for evading detection. The only thing
    that moves this number is the user actually writing about this job.
    """
    headers = await register_and_login(client)
    await setup_profile(client, headers)
    first = await save_posting(client, headers, POSTING, "Senior Backend Engineer")
    second = await save_posting(
        client, headers, OTHER_POSTING, "Staff Platform Engineer"
    )

    kept = (await client.post(f"/jobs/{first}/cover-letter", headers=headers)).json()
    await client.put(
        f"/jobs/{first}/cover-letter", headers=headers, json={"body": kept["body"]}
    )

    written = (
        "I read the posting about owning the deployment pipeline and wanted to write. "
        "Last winter I moved a billing system off a shared monolith, which meant "
        "rebuilding the release path from scratch under a freeze. I would like to do "
        "that kind of work again, and your team seems to be in the middle of it."
    )
    saved = await client.put(
        f"/jobs/{second}/cover-letter", headers=headers, json={"body": written}
    )

    assert saved.json()["similarity"] < 20
    assert saved.json()["similarity_warning"] is False


async def test_saving_replaces_rather_than_accumulates(client: AsyncClient) -> None:
    """Similarity against earlier attempts at the same letter would measure nothing."""
    headers = await register_and_login(client)
    await setup_profile(client, headers)
    posting_id = await save_posting(client, headers, POSTING, "Senior Backend Engineer")

    await client.put(
        f"/jobs/{posting_id}/cover-letter", headers=headers, json={"body": "First go."}
    )
    second = await client.put(
        f"/jobs/{posting_id}/cover-letter",
        headers=headers,
        json={"body": "Second go, completely rewritten."},
    )

    assert second.status_code == 200
    assert second.json()["body"] == "Second go, completely rewritten."
    # Its own earlier draft is not part of the corpus it is measured against.
    assert second.json()["similarity"] == 0


async def test_a_saved_letter_still_carrying_the_placeholder_says_so(
    client: AsyncClient,
) -> None:
    """Sending a letter with the unwritten paragraph still in it is embarrassing."""
    headers = await register_and_login(client)
    await setup_profile(client, headers)
    posting_id = await save_posting(client, headers, POSTING, "Senior Backend Engineer")

    draft = (
        await client.post(f"/jobs/{posting_id}/cover-letter", headers=headers)
    ).json()
    saved = await client.put(
        f"/jobs/{posting_id}/cover-letter",
        headers=headers,
        json={"body": draft["body"]},
    )

    assert saved.json()["needs_writing"] is True


async def test_letters_are_per_user(client: AsyncClient) -> None:
    """One account's letters are not another's corpus, nor another's to read."""
    owner = await register_and_login(client, email="owner@example.com")
    await setup_profile(client, owner)
    posting_id = await save_posting(client, owner, POSTING, "Senior Backend Engineer")
    intruder = await register_and_login(client, email="intruder@example.com")

    assert (
        await client.post(f"/jobs/{posting_id}/cover-letter", headers=intruder)
    ).status_code == 404
    assert (
        await client.put(
            f"/jobs/{posting_id}/cover-letter",
            headers=intruder,
            json={"body": "Hello."},
        )
    ).status_code == 404


async def test_cover_letters_require_authentication(client: AsyncClient) -> None:
    """Built from personal data, so none of this is anonymous."""
    assert (await client.post("/jobs/1/cover-letter")).status_code == 401
    assert (
        await client.put("/jobs/1/cover-letter", json={"body": "Hello."})
    ).status_code == 401
