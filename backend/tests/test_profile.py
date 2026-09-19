import json

from httpx import AsyncClient

from tests.conftest import FakeLLMClient
from tests.helpers import register_and_login, upload_cv


async def add_experience(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    title: str = "Backend Engineer",
    organisation: str = "Acme",
    start_date: str = "2021-03-01",
    end_date: str | None = "2024-06-01",
) -> int:
    """Add a role and return its id.

    Args:
        client: The test HTTP client.
        headers: Authorization headers.
        title: Role title.
        organisation: Employer.
        start_date: ISO start date.
        end_date: ISO end date, or ``None`` for a current role.

    Returns:
        The created role's id.
    """
    response = await client.post(
        "/profile/experiences",
        headers=headers,
        json={
            "organisation": organisation,
            "title": title,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    experience_id: int = response.json()["id"]
    return experience_id


async def test_profile_is_created_on_first_access(client: AsyncClient) -> None:
    """A new user has an empty profile rather than a missing one."""
    headers = await register_and_login(client)

    response = await client.get("/profile", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["experiences"] == []
    assert body["skills"] == []


async def test_profile_requires_authentication(client: AsyncClient) -> None:
    """The profile is not readable anonymously."""
    assert (await client.get("/profile")).status_code == 401


async def test_profile_fields_can_be_updated(client: AsyncClient) -> None:
    """A partial update changes only what was sent."""
    headers = await register_and_login(client)
    await client.patch("/profile", headers=headers, json={"headline": "Engineer"})

    response = await client.patch(
        "/profile", headers=headers, json={"location": "Porto"}
    )

    body = response.json()
    assert body["headline"] == "Engineer"
    assert body["location"] == "Porto"


async def test_add_experience(client: AsyncClient) -> None:
    """A role is added to the profile and returned in it."""
    headers = await register_and_login(client)

    await add_experience(client, headers)

    profile = (await client.get("/profile", headers=headers)).json()
    assert len(profile["experiences"]) == 1
    assert profile["experiences"][0]["title"] == "Backend Engineer"


async def test_a_role_without_an_end_date_is_current(client: AsyncClient) -> None:
    """Absence of an end date is the single source of truth for "current"."""
    headers = await register_and_login(client)

    await add_experience(client, headers, end_date=None)

    profile = (await client.get("/profile", headers=headers)).json()
    assert profile["experiences"][0]["is_current"] is True


async def test_end_date_before_start_is_rejected(client: AsyncClient) -> None:
    """Dates the wrong way round fail validation."""
    headers = await register_and_login(client)

    response = await client.post(
        "/profile/experiences",
        headers=headers,
        json={
            "organisation": "Acme",
            "title": "Engineer",
            "start_date": "2024-01-01",
            "end_date": "2021-01-01",
        },
    )

    assert response.status_code == 422


async def test_experiences_are_returned_newest_first(client: AsyncClient) -> None:
    """Ordering is what a CV needs, so it belongs in the model, not the client."""
    headers = await register_and_login(client)
    await add_experience(client, headers, title="Older", start_date="2015-01-01")
    await add_experience(client, headers, title="Newer", start_date="2022-01-01")

    profile = (await client.get("/profile", headers=headers)).json()

    assert [e["title"] for e in profile["experiences"]] == ["Newer", "Older"]


async def test_delete_experience(client: AsyncClient) -> None:
    """A role can be removed."""
    headers = await register_and_login(client)
    experience_id = await add_experience(client, headers)

    response = await client.delete(
        f"/profile/experiences/{experience_id}", headers=headers
    )

    assert response.status_code == 204
    assert (await client.get("/profile", headers=headers)).json()["experiences"] == []


async def test_cannot_delete_another_users_experience(client: AsyncClient) -> None:
    """Profiles are isolated between users."""
    owner = await register_and_login(client, email="owner@example.com")
    experience_id = await add_experience(client, owner)
    intruder = await register_and_login(client, email="intruder@example.com")

    response = await client.delete(
        f"/profile/experiences/{experience_id}", headers=intruder
    )

    assert response.status_code == 404


async def test_add_education(client: AsyncClient) -> None:
    """A qualification is added to the profile."""
    headers = await register_and_login(client)

    response = await client.post(
        "/profile/educations",
        headers=headers,
        json={
            "institution": "University of Porto",
            "qualification": "BSc",
            "field_of_study": "Computer Science",
            "end_date": "2016-07-01",
        },
    )

    assert response.status_code == 201
    profile = (await client.get("/profile", headers=headers)).json()
    assert profile["educations"][0]["qualification"] == "BSc"


async def test_add_skill_stores_the_canonical_form(client: AsyncClient) -> None:
    """The user's spelling is kept, and the matchable form is derived from it."""
    headers = await register_and_login(client)

    response = await client.post(
        "/profile/skills", headers=headers, json={"name": "K8s"}
    )

    body = response.json()
    assert body["name"] == "K8s"
    assert body["canonical_name"] == "kubernetes"


async def test_duplicate_skills_are_rejected_on_the_canonical_form(
    client: AsyncClient,
) -> None:
    """Adding "Kubernetes" after "K8s" is a duplicate, not a second skill."""
    headers = await register_and_login(client)
    await client.post("/profile/skills", headers=headers, json={"name": "K8s"})

    response = await client.post(
        "/profile/skills", headers=headers, json={"name": "Kubernetes"}
    )

    assert response.status_code == 400


async def test_skill_can_cite_evidence(client: AsyncClient) -> None:
    """A skill backed by a role is marked as evidenced."""
    headers = await register_and_login(client)
    experience_id = await add_experience(client, headers)

    response = await client.post(
        "/profile/skills",
        headers=headers,
        json={"name": "Python", "evidence_experience_ids": [experience_id]},
    )

    body = response.json()
    assert body["is_evidenced"] is True
    assert body["evidence_experience_ids"] == [experience_id]


async def test_skill_without_evidence_is_flagged_as_unevidenced(
    client: AsyncClient,
) -> None:
    """An unbacked claim is representable, but distinguishable.

    This is what lets a CV generator honour *never fabricate experience*: it can tell a
    skill grounded in a dated role from one the user merely asserted.
    """
    headers = await register_and_login(client)

    response = await client.post(
        "/profile/skills", headers=headers, json={"name": "Rust"}
    )

    assert response.json()["is_evidenced"] is False


async def test_cannot_cite_another_users_experience_as_evidence(
    client: AsyncClient,
) -> None:
    """Evidence must come from the caller's own profile."""
    owner = await register_and_login(client, email="owner@example.com")
    experience_id = await add_experience(client, owner)
    intruder = await register_and_login(client, email="intruder@example.com")

    response = await client.post(
        "/profile/skills",
        headers=intruder,
        json={"name": "Python", "evidence_experience_ids": [experience_id]},
    )

    assert response.status_code == 400


async def test_deleting_a_role_does_not_delete_the_skill(client: AsyncClient) -> None:
    """Removing a role drops its evidence link, leaving the skill unevidenced."""
    headers = await register_and_login(client)
    experience_id = await add_experience(client, headers)
    await client.post(
        "/profile/skills",
        headers=headers,
        json={"name": "Python", "evidence_experience_ids": [experience_id]},
    )

    await client.delete(f"/profile/experiences/{experience_id}", headers=headers)

    profile = (await client.get("/profile", headers=headers)).json()
    assert len(profile["skills"]) == 1
    assert profile["skills"][0]["is_evidenced"] is False


async def test_delete_skill(client: AsyncClient) -> None:
    """A skill can be removed."""
    headers = await register_and_login(client)
    skill_id = (
        await client.post("/profile/skills", headers=headers, json={"name": "Python"})
    ).json()["id"]

    response = await client.delete(f"/profile/skills/{skill_id}", headers=headers)

    assert response.status_code == 204
    assert (await client.get("/profile", headers=headers)).json()["skills"] == []


async def test_skill_years_must_be_plausible(client: AsyncClient) -> None:
    """A negative or absurd number of years fails validation."""
    headers = await register_and_login(client)

    response = await client.post(
        "/profile/skills", headers=headers, json={"name": "Python", "years": -3}
    )

    assert response.status_code == 422


async def test_import_from_cv_requires_authentication(client: AsyncClient) -> None:
    """Extraction reads a stored document, so it is never anonymous."""
    assert (await client.post("/profile/import-from-cv/1")).status_code == 401


async def test_import_from_cv_rejects_a_cv_the_user_does_not_own(
    client: AsyncClient,
) -> None:
    """Ownership is enforced in the query, so another account's CV is simply absent."""
    owner = await register_and_login(client, email="owner@example.com")
    cv_id = await upload_cv(client, owner)

    intruder = await register_and_login(client, email="intruder@example.com")

    response = await client.post(f"/profile/import-from-cv/{cv_id}", headers=intruder)

    assert response.status_code == 404


async def test_import_from_cv_proposes_without_persisting(client: AsyncClient) -> None:
    """The endpoint returns candidates and writes nothing.

    Load-bearing: extraction guesses, so a result that reached the profile on its own
    would put invented history behind every CV generated from it. The user confirms
    through the ordinary create endpoints instead.
    """
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)

    response = await client.post(f"/profile/import-from-cv/{cv_id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "contact",
        "headline",
        "summary",
        "location",
        "experiences",
        "educations",
        "skills",
    }

    # The blank test PDF yields nothing, which is a valid outcome — and either way the
    # profile must be untouched.
    profile = (await client.get("/profile", headers=headers)).json()
    assert profile["experiences"] == []
    assert profile["educations"] == []
    assert profile["skills"] == []


async def test_summary_is_a_proposal_and_is_not_saved(
    client: AsyncClient, fake_llm: FakeLLMClient
) -> None:
    """The draft comes back to the caller and the profile is untouched.

    The same rule as `/import-from-cv`, and for the same reason: a generated sentence
    is not a profile fact until a person has read it and pressed save.
    """
    headers = await register_and_login(client)
    await add_experience(client, headers)
    fake_llm.response = json.dumps({"summary": "Backend engineer working on Acme."})

    response = await client.post("/profile/summary", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"summary": "Backend engineer working on Acme."}
    assert (await client.get("/profile", headers=headers)).json()["summary"] is None


async def test_summary_prompt_carries_the_profile_facts(
    client: AsyncClient, fake_llm: FakeLLMClient
) -> None:
    """What the model may say is bounded by what it was given."""
    headers = await register_and_login(client)
    await add_experience(
        client, headers, title="Platform Engineer", organisation="Zeta"
    )
    fake_llm.response = json.dumps({"summary": "A summary."})

    await client.post("/profile/summary", headers=headers)

    _system, user_prompt = fake_llm.calls[0]
    assert "Platform Engineer" in user_prompt
    assert "Zeta" in user_prompt


async def test_summary_refuses_an_empty_profile_without_calling_the_model(
    client: AsyncClient, fake_llm: FakeLLMClient
) -> None:
    """There is nothing to summarise, so the only possible summary is invented.

    The guard is deterministic and sits in front of the model rather than in the
    prompt: an instruction not to make things up is a request, and this is a rule.
    """
    headers = await register_and_login(client)

    response = await client.post("/profile/summary", headers=headers)

    assert response.status_code == 400
    assert "not enough" in response.json()["detail"]
    assert fake_llm.calls == []


async def test_summary_rejects_output_that_fails_validation_twice(
    client: AsyncClient, fake_llm: FakeLLMClient
) -> None:
    """An unusable draft is an error, not an empty summary shown as a suggestion."""
    headers = await register_and_login(client)
    await add_experience(client, headers)
    fake_llm.response = json.dumps({"nonsense": True})

    response = await client.post("/profile/summary", headers=headers)

    assert response.status_code == 502
    assert len(fake_llm.calls) == 2


async def test_skill_evidence_can_be_set_after_the_fact(client: AsyncClient) -> None:
    """The gap that made "evidence N skills" an impossible task.

    Evidence used to be settable only when a skill was created, and the CV importer
    creates them with none — so every skill in the product stayed unevidenced, the
    readiness score could never reach 100, and the CV generator omitted all of them.
    """
    headers = await register_and_login(client)
    experience_id = await add_experience(client, headers)
    skill_id = (
        await client.post("/profile/skills", headers=headers, json={"name": "Python"})
    ).json()["id"]

    response = await client.patch(
        f"/profile/skills/{skill_id}",
        headers=headers,
        json={"evidence_experience_ids": [experience_id]},
    )

    assert response.status_code == 200
    assert response.json()["is_evidenced"] is True
    assert response.json()["evidence_experience_ids"] == [experience_id]


async def test_skill_evidence_is_replaced_not_merged(client: AsyncClient) -> None:
    """Removing a citation has to be as ordinary an edit as adding one."""
    headers = await register_and_login(client)
    experience_id = await add_experience(client, headers)
    skill_id = (
        await client.post(
            "/profile/skills",
            headers=headers,
            json={"name": "Python", "evidence_experience_ids": [experience_id]},
        )
    ).json()["id"]

    response = await client.patch(
        f"/profile/skills/{skill_id}",
        headers=headers,
        json={"evidence_experience_ids": []},
    )

    assert response.json()["is_evidenced"] is False


async def test_skill_evidence_refuses_another_users_role(client: AsyncClient) -> None:
    """Evidence is the grounding claim; citing a stranger's role would fabricate it."""
    owner = await register_and_login(client)
    experience_id = await add_experience(client, owner)
    intruder = await register_and_login(client, email="intruder@example.com")
    skill_id = (
        await client.post("/profile/skills", headers=intruder, json={"name": "Python"})
    ).json()["id"]

    response = await client.patch(
        f"/profile/skills/{skill_id}",
        headers=intruder,
        json={"evidence_experience_ids": [experience_id]},
    )

    assert response.status_code == 400


async def test_a_role_can_be_amended_in_place(client: AsyncClient) -> None:
    """A typo in an employer name should not mean deleting the row and retyping it."""
    headers = await register_and_login(client)
    experience_id = await add_experience(client, headers, organisation="Acme")

    response = await client.patch(
        f"/profile/experiences/{experience_id}",
        headers=headers,
        json={"organisation": "Acme Corp"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["organisation"] == "Acme Corp"
    # Untouched fields stay untouched — the whole point of PATCH over PUT here.
    assert body["title"] == "Backend Engineer"


async def test_amending_a_role_checks_dates_against_the_stored_ones(
    client: AsyncClient,
) -> None:
    """Changing one date of a pair is ordinary, and the schema sees only one."""
    headers = await register_and_login(client)
    experience_id = await add_experience(
        client, headers, start_date="2021-03-01", end_date="2024-06-01"
    )

    response = await client.patch(
        f"/profile/experiences/{experience_id}",
        headers=headers,
        json={"end_date": "2020-01-01"},
    )

    assert response.status_code == 400


async def test_a_qualification_can_be_amended_in_place(client: AsyncClient) -> None:
    """Same rule for education."""
    headers = await register_and_login(client)
    created = await client.post(
        "/profile/educations",
        headers=headers,
        json={"institution": "Uni", "qualification": "BSc"},
    )

    response = await client.patch(
        f"/profile/educations/{created.json()['id']}",
        headers=headers,
        json={"field_of_study": "Computer Science"},
    )

    assert response.status_code == 200
    assert response.json()["field_of_study"] == "Computer Science"
