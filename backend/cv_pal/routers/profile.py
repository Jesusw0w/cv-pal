from fastapi import APIRouter, status

from cv_pal.dependencies import CurrentUser, DbSession, LLMClientDep
from cv_pal.models import CareerProfile, Skill
from cv_pal.schemas import (
    CareerGoalsResponse,
    CareerGoalsUpdate,
    CareerProfileResponse,
    CareerProfileUpdate,
    CvExtractionResponse,
    EducationCreate,
    EducationResponse,
    EducationUpdate,
    EvidenceSuggestionResponse,
    ExperienceCreate,
    ExperienceResponse,
    ExperienceUpdate,
    ProfileSummaryResponse,
    SkillCreate,
    SkillResponse,
    SkillUpdate,
)
from cv_pal.services import profile_service

router = APIRouter(prefix="/profile", tags=["profile"])


def _skill_response(skill: Skill) -> SkillResponse:
    """Shape a skill for the API, including its evidence references.

    Args:
        skill: The skill to serialise.

    Returns:
        The response model.
    """
    return SkillResponse(
        id=skill.id,
        name=skill.name,
        canonical_name=skill.canonical_name,
        category=skill.category,
        proficiency=skill.proficiency,
        years=skill.years,
        is_evidenced=skill.is_evidenced,
        evidence_experience_ids=[e.id for e in skill.evidence],
    )


def _profile_response(profile: CareerProfile) -> CareerProfileResponse:
    """Shape the whole profile for the API.

    Args:
        profile: The profile to serialise.

    Returns:
        The response model.
    """
    return CareerProfileResponse(
        id=profile.id,
        headline=profile.headline,
        summary=profile.summary,
        location=profile.location,
        phone=profile.phone,
        website_url=profile.website_url,
        linkedin_url=profile.linkedin_url,
        experiences=[ExperienceResponse.model_validate(e) for e in profile.experiences],
        educations=[EducationResponse.model_validate(e) for e in profile.educations],
        skills=[_skill_response(s) for s in profile.skills],
    )


@router.get("", response_model=CareerProfileResponse)
async def get_profile(
    current_user: CurrentUser, db: DbSession
) -> CareerProfileResponse:
    """Get the current user's career profile.

    An empty profile is created on first access, so the client never has to handle
    "not created yet" as a distinct state.

    Returns:
        The profile with its experiences, educations and skills.
    """
    profile = await profile_service.get_or_create_profile(db, user_id=current_user.id)
    return _profile_response(profile)


@router.patch("", response_model=CareerProfileResponse)
async def update_profile(
    payload: CareerProfileUpdate, current_user: CurrentUser, db: DbSession
) -> CareerProfileResponse:
    """Update the profile's own fields.

    Args:
        payload: The fields to change; omitted fields are left alone.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The updated profile.
    """
    profile = await profile_service.update_profile(
        db, user_id=current_user.id, payload=payload
    )
    return _profile_response(profile)


@router.post("/import-from-cv/{cv_id}", response_model=CvExtractionResponse)
async def import_from_cv(
    cv_id: int,
    current_user: CurrentUser,
    db: DbSession,
    client: LLMClientDep,
    enrich: bool = True,
) -> CvExtractionResponse:
    """Read structured records out of an uploaded CV, without storing any of them.

    The response is a **proposal**: the client shows it, the user confirms what is
    right, and the confirmed records are created through the ordinary
    `/profile/experiences`, `/profile/educations` and `/profile/skills` endpoints. No
    extraction result reaches the profile without a person agreeing to it.

    Runs with no language model configured — the deterministic pass is the answer, and
    the model only ever complements it. This endpoint therefore never fails because of
    the model: `enriched` in the response says whether one contributed.

    Args:
        cv_id: The CV to read.
        current_user: The authenticated user.
        db: Async database session.
        client: The configured language model client.
        enrich: Whether to let a model complement the deterministic read. Pass false
            to force the deterministic pass alone — it is faster and reproducible.

    Returns:
        The extracted proposal.
    """
    extracted = await profile_service.extract_from_cv(
        db, user_id=current_user.id, cv_id=cv_id, client=client if enrich else None
    )
    return CvExtractionResponse.model_validate(extracted)


@router.post("/summary", response_model=ProfileSummaryResponse)
async def generate_summary(
    current_user: CurrentUser, db: DbSession, client: LLMClientDep
) -> ProfileSummaryResponse:
    """Draft a professional summary from the facts already in the profile.

    A **proposal**, like `/import-from-cv`: nothing is stored, and saving it is an
    ordinary `PATCH /profile`. The one profile endpoint that needs a model.

    Args:
        current_user: The authenticated user.
        db: Async database session.
        client: The configured language model client.

    Returns:
        The proposed summary.

    Raises:
        EmptyProfileError: If there are no roles and no skills to write from.
        LLMError: If the model is unreachable or its output is unusable.
    """
    return await profile_service.generate_summary(
        db, user_id=current_user.id, client=client
    )


@router.get("/goals", response_model=CareerGoalsResponse)
async def get_goals(current_user: CurrentUser, db: DbSession) -> CareerGoalsResponse:
    """Get what the current user is looking for.

    An empty record is created on first access, so the client never has to handle
    "not set yet" as a distinct state.

    Returns:
        The user's career goals.
    """
    goals = await profile_service.get_or_create_goals(db, user_id=current_user.id)
    return CareerGoalsResponse.model_validate(goals)


@router.put("/goals", response_model=CareerGoalsResponse)
async def replace_goals(
    payload: CareerGoalsUpdate, current_user: CurrentUser, db: DbSession
) -> CareerGoalsResponse:
    """Replace what the current user is looking for.

    A replace rather than a merge: an omitted preference means the user cleared it.

    Args:
        payload: The complete new set of goals.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The stored goals.
    """
    goals = await profile_service.replace_goals(
        db, user_id=current_user.id, payload=payload
    )
    return CareerGoalsResponse.model_validate(goals)


@router.post(
    "/experiences",
    response_model=ExperienceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_experience(
    payload: ExperienceCreate, current_user: CurrentUser, db: DbSession
) -> ExperienceResponse:
    """Add a role to the profile.

    Args:
        payload: The role to add. Omit ``end_date`` to mark it as current.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The created role.
    """
    experience = await profile_service.add_experience(
        db, user_id=current_user.id, payload=payload
    )
    return ExperienceResponse.model_validate(experience)


@router.patch("/experiences/{experience_id}", response_model=ExperienceResponse)
async def update_experience(
    experience_id: int,
    payload: ExperienceUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> ExperienceResponse:
    """Amend a role.

    Args:
        experience_id: The role to amend.
        payload: The fields to change; omitted fields are left alone.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The updated role.

    Raises:
        NotFoundError: If the role is not on this user's profile.
    """
    experience = await profile_service.update_experience(
        db, user_id=current_user.id, experience_id=experience_id, payload=payload
    )
    return ExperienceResponse.model_validate(experience)


@router.delete("/experiences/{experience_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_experience(
    experience_id: int, current_user: CurrentUser, db: DbSession
) -> None:
    """Remove a role from the profile.

    Args:
        experience_id: The role to remove.
        current_user: The authenticated user.
        db: Async database session.

    Raises:
        NotFoundError: If the role is not on this user's profile.
    """
    await profile_service.delete_experience(
        db, user_id=current_user.id, experience_id=experience_id
    )


@router.post(
    "/educations", response_model=EducationResponse, status_code=status.HTTP_201_CREATED
)
async def add_education(
    payload: EducationCreate, current_user: CurrentUser, db: DbSession
) -> EducationResponse:
    """Add a qualification to the profile.

    Args:
        payload: The qualification to add.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The created qualification.
    """
    education = await profile_service.add_education(
        db, user_id=current_user.id, payload=payload
    )
    return EducationResponse.model_validate(education)


@router.patch("/educations/{education_id}", response_model=EducationResponse)
async def update_education(
    education_id: int,
    payload: EducationUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> EducationResponse:
    """Amend a qualification.

    Args:
        education_id: The qualification to amend.
        payload: The fields to change; omitted fields are left alone.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The updated qualification.

    Raises:
        NotFoundError: If it is not on this user's profile.
    """
    education = await profile_service.update_education(
        db, user_id=current_user.id, education_id=education_id, payload=payload
    )
    return EducationResponse.model_validate(education)


@router.delete("/educations/{education_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_education(
    education_id: int, current_user: CurrentUser, db: DbSession
) -> None:
    """Remove a qualification from the profile.

    Args:
        education_id: The qualification to remove.
        current_user: The authenticated user.
        db: Async database session.

    Raises:
        NotFoundError: If it is not on this user's profile.
    """
    await profile_service.delete_education(
        db, user_id=current_user.id, education_id=education_id
    )


@router.post(
    "/skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED
)
async def add_skill(
    payload: SkillCreate, current_user: CurrentUser, db: DbSession
) -> SkillResponse:
    """Add a skill to the profile, optionally citing the roles that evidence it.

    Args:
        payload: The skill to add.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The created skill.

    Raises:
        ConflictError: If the profile already claims this skill.
        ValidationError: If a cited role is not on this user's profile.
    """
    skill = await profile_service.add_skill(
        db, user_id=current_user.id, payload=payload
    )
    return _skill_response(skill)


@router.get(
    "/skills/evidence-suggestions", response_model=list[EvidenceSuggestionResponse]
)
async def suggest_skill_evidence(
    current_user: CurrentUser, db: DbSession
) -> list[EvidenceSuggestionResponse]:
    """Propose citations for skills the user's own role descriptions already name.

    Declared before `/skills/{skill_id}` for the usual reason: otherwise the path is
    read as a skill id.

    Writes nothing. A skill with no dated role behind it cannot appear in a generated
    CV, and after a CV import there are usually twenty of them — this finds the
    citations that are already sitting in the descriptions rather than asking the user
    to re-enter what they wrote.

    Returns:
        One entry per skill with roles worth citing.
    """
    profile = await profile_service.get_or_create_profile(db, user_id=current_user.id)
    roles = {experience.id: experience for experience in profile.experiences}
    names = {skill.id: skill.name for skill in profile.skills}

    suggestions = await profile_service.suggest_skill_evidence(
        db, user_id=current_user.id
    )
    return [
        EvidenceSuggestionResponse(
            skill_id=found.skill_id,
            skill_name=names[found.skill_id],
            experience_ids=list(found.experience_ids),
            experience_labels=[
                f"{roles[role_id].title}, {roles[role_id].organisation}"
                for role_id in found.experience_ids
            ],
        )
        for found in suggestions
    ]


@router.patch("/skills/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: int, payload: SkillUpdate, current_user: CurrentUser, db: DbSession
) -> SkillResponse:
    """Amend a skill, including which roles evidence it.

    The only way to evidence a skill after creation, and the CV importer creates them
    with none — so this is what makes "evidence N skills" a task that can be finished.

    Args:
        skill_id: The skill to amend.
        payload: The fields to change. `evidence_experience_ids`, when given, replaces
            the citations rather than adding to them.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The updated skill.

    Raises:
        NotFoundError: If the skill is not on this user's profile.
        ValidationError: If a cited role is not on this user's profile.
        ConflictError: If the new name collides with an existing skill.
    """
    skill = await profile_service.update_skill(
        db, user_id=current_user.id, skill_id=skill_id, payload=payload
    )
    return _skill_response(skill)


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(skill_id: int, current_user: CurrentUser, db: DbSession) -> None:
    """Remove a skill from the profile.

    Args:
        skill_id: The skill to remove.
        current_user: The authenticated user.
        db: Async database session.

    Raises:
        NotFoundError: If it is not on this user's profile.
    """
    await profile_service.delete_skill(db, user_id=current_user.id, skill_id=skill_id)
