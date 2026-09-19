"""The career profile: the structured record everything else is generated from.

Ownership is enforced by resolving the profile from the user on every call, so a request
can only ever reach rows hanging off that user's own profile. No endpoint accepts a
profile id from the caller.
"""

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cv_pal.analysis.evidence import (
    EvidenceSuggestion,
    ExperienceFacts,
    SkillFacts,
    suggest_evidence,
)
from cv_pal.analysis.extraction import ExtractedProfile, extract_profile
from cv_pal.analysis.keywords import canonical
from cv_pal.constants import (
    DEFAULT_ERROR_EDUCATION_NOT_FOUND,
    DEFAULT_ERROR_END_BEFORE_START,
    DEFAULT_ERROR_EVIDENCE_NOT_OWNED,
    DEFAULT_ERROR_EXPERIENCE_NOT_FOUND,
    DEFAULT_ERROR_SKILL_DUPLICATE,
    DEFAULT_ERROR_SKILL_NOT_FOUND,
)
from cv_pal.exceptions import (
    ConflictError,
    EmptyProfileError,
    NotFoundError,
    ValidationError,
)
from cv_pal.llm import LLMClient, complete_validated
from cv_pal.models import CareerGoals, CareerProfile, Education, Experience, Skill
from cv_pal.parsing import extract_cv_text
from cv_pal.prompts import (
    PROFILE_SUMMARY_RETRY_PROMPT,
    PROFILE_SUMMARY_SYSTEM_PROMPT,
    PROFILE_SUMMARY_USER_PROMPT,
)
from cv_pal.schemas import (
    CareerGoalsUpdate,
    CareerProfileUpdate,
    EducationCreate,
    EducationUpdate,
    ExperienceCreate,
    ExperienceUpdate,
    ProfileSummaryResponse,
    SkillCreate,
    SkillUpdate,
)
from cv_pal.services.cv_service import get_owned_cv


async def get_or_create_profile(db: AsyncSession, *, user_id: int) -> CareerProfile:
    """Return the user's profile, creating an empty one on first access.

    Creating on read means the client never has to handle "no profile yet" as a separate
    state — there is always somewhere to add the first role.

    Args:
        db: Async database session.
        user_id: The owning user.

    Returns:
        The user's career profile with its collections loaded.
    """
    result = await db.execute(
        select(CareerProfile)
        .where(CareerProfile.user_id == user_id)
        .options(
            selectinload(CareerProfile.experiences),
            selectinload(CareerProfile.educations),
            selectinload(CareerProfile.skills).selectinload(Skill.evidence),
        )
    )
    profile = result.scalar_one_or_none()
    if profile is not None:
        return profile

    profile = CareerProfile(user_id=user_id)
    db.add(profile)
    await db.commit()
    return await get_or_create_profile(db, user_id=user_id)


async def update_profile(
    db: AsyncSession, *, user_id: int, payload: CareerProfileUpdate
) -> CareerProfile:
    """Apply a partial update to the profile's own fields.

    Args:
        db: Async database session.
        user_id: The owning user.
        payload: The fields to change; omitted fields are left alone.

    Returns:
        The updated profile.
    """
    profile = await get_or_create_profile(db, user_id=user_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    await db.commit()
    return await get_or_create_profile(db, user_id=user_id)


async def add_experience(
    db: AsyncSession, *, user_id: int, payload: ExperienceCreate
) -> Experience:
    """Add a role to the profile.

    Args:
        db: Async database session.
        user_id: The owning user.
        payload: The role to add.

    Returns:
        The created role.
    """
    profile = await get_or_create_profile(db, user_id=user_id)
    experience = Experience(profile_id=profile.id, **payload.model_dump())
    db.add(experience)
    await db.commit()
    await db.refresh(experience)
    return experience


async def _owned_experience(
    db: AsyncSession, *, user_id: int, experience_id: int
) -> Experience:
    """Fetch a role belonging to the user's profile.

    Args:
        db: Async database session.
        user_id: The owning user.
        experience_id: The role to fetch.

    Returns:
        The role.

    Raises:
        NotFoundError: If it does not exist on this user's profile.
    """
    result = await db.execute(
        select(Experience)
        .join(CareerProfile, CareerProfile.id == Experience.profile_id)
        .where(Experience.id == experience_id, CareerProfile.user_id == user_id)
    )
    experience = result.scalar_one_or_none()
    if experience is None:
        raise NotFoundError(DEFAULT_ERROR_EXPERIENCE_NOT_FOUND)
    return experience


async def update_experience(
    db: AsyncSession, *, user_id: int, experience_id: int, payload: ExperienceUpdate
) -> Experience:
    """Amend a role.

    Args:
        db: Async database session.
        user_id: The owning user.
        experience_id: The role to amend.
        payload: The fields to change; omitted fields are left alone.

    Returns:
        The updated role.

    Raises:
        NotFoundError: If it does not exist on this user's profile.
        ValidationError: If the amendment leaves the end date before the start.
    """
    experience = await _owned_experience(
        db, user_id=user_id, experience_id=experience_id
    )
    changes = payload.model_dump(exclude_unset=True)

    # The schema only sees the dates it was sent, and changing one of a pair is the
    # ordinary edit.
    start = changes.get("start_date", experience.start_date)
    end = changes.get("end_date", experience.end_date)
    if start is not None and end is not None and end < start:
        raise ValidationError(DEFAULT_ERROR_END_BEFORE_START)

    for field, value in changes.items():
        setattr(experience, field, value)
    await db.commit()
    await db.refresh(experience)
    return experience


async def delete_experience(
    db: AsyncSession, *, user_id: int, experience_id: int
) -> None:
    """Remove a role from the profile.

    Args:
        db: Async database session.
        user_id: The owning user.
        experience_id: The role to remove.

    Raises:
        NotFoundError: If it does not exist on this user's profile.
    """
    experience = await _owned_experience(
        db, user_id=user_id, experience_id=experience_id
    )
    await db.delete(experience)
    await db.commit()


async def add_education(
    db: AsyncSession, *, user_id: int, payload: EducationCreate
) -> Education:
    """Add a qualification to the profile.

    Args:
        db: Async database session.
        user_id: The owning user.
        payload: The qualification to add.

    Returns:
        The created qualification.
    """
    profile = await get_or_create_profile(db, user_id=user_id)
    education = Education(profile_id=profile.id, **payload.model_dump())
    db.add(education)
    await db.commit()
    await db.refresh(education)
    return education


async def _owned_education(
    db: AsyncSession, *, user_id: int, education_id: int
) -> Education:
    """Fetch a qualification belonging to the user's profile.

    Args:
        db: Async database session.
        user_id: The owning user.
        education_id: The qualification to fetch.

    Returns:
        The qualification.

    Raises:
        NotFoundError: If it does not exist on this user's profile.
    """
    result = await db.execute(
        select(Education)
        .join(CareerProfile, CareerProfile.id == Education.profile_id)
        .where(Education.id == education_id, CareerProfile.user_id == user_id)
    )
    education = result.scalar_one_or_none()
    if education is None:
        raise NotFoundError(DEFAULT_ERROR_EDUCATION_NOT_FOUND)
    return education


async def delete_education(
    db: AsyncSession, *, user_id: int, education_id: int
) -> None:
    """Remove a qualification from the profile.

    Args:
        db: Async database session.
        user_id: The owning user.
        education_id: The qualification to remove.

    Raises:
        NotFoundError: If it does not exist on this user's profile.
    """
    education = await _owned_education(db, user_id=user_id, education_id=education_id)
    await db.delete(education)
    await db.commit()


async def update_education(
    db: AsyncSession, *, user_id: int, education_id: int, payload: EducationUpdate
) -> Education:
    """Amend a qualification.

    Args:
        db: Async database session.
        user_id: The owning user.
        education_id: The qualification to amend.
        payload: The fields to change; omitted fields are left alone.

    Returns:
        The updated qualification.

    Raises:
        NotFoundError: If it does not exist on this user's profile.
    """
    education = await _owned_education(db, user_id=user_id, education_id=education_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(education, field, value)
    await db.commit()
    await db.refresh(education)
    return education


async def add_skill(db: AsyncSession, *, user_id: int, payload: SkillCreate) -> Skill:
    """Add a skill to the profile, with the roles that evidence it.

    The canonical form is stored alongside the user's spelling, so "K8s" and
    "Kubernetes" deduplicate and both match a posting asking for either.

    Args:
        db: Async database session.
        user_id: The owning user.
        payload: The skill to add.

    Returns:
        The created skill with its evidence loaded.

    Raises:
        ConflictError: If the profile already claims this skill.
        ValidationError: If a cited role is not on this user's profile.
    """
    profile = await get_or_create_profile(db, user_id=user_id)
    evidence = await _resolve_evidence(
        db, user_id=user_id, experience_ids=payload.evidence_experience_ids
    )

    skill = Skill(
        profile_id=profile.id,
        name=payload.name,
        canonical_name=canonical(payload.name),
        category=payload.category,
        proficiency=payload.proficiency,
        years=payload.years,
        evidence=evidence,
    )
    db.add(skill)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(DEFAULT_ERROR_SKILL_DUPLICATE) from exc

    result = await db.execute(
        select(Skill).where(Skill.id == skill.id).options(selectinload(Skill.evidence))
    )
    return result.scalar_one()


async def _owned_skill(db: AsyncSession, *, user_id: int, skill_id: int) -> Skill:
    """Fetch a skill belonging to the user's profile.

    Args:
        db: Async database session.
        user_id: The owning user.
        skill_id: The skill to fetch.

    Returns:
        The skill, with its evidence loaded.

    Raises:
        NotFoundError: If it does not exist on this user's profile.
    """
    result = await db.execute(
        select(Skill)
        .join(CareerProfile, CareerProfile.id == Skill.profile_id)
        .where(Skill.id == skill_id, CareerProfile.user_id == user_id)
        .options(selectinload(Skill.evidence))
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise NotFoundError(DEFAULT_ERROR_SKILL_NOT_FOUND)
    return skill


async def delete_skill(db: AsyncSession, *, user_id: int, skill_id: int) -> None:
    """Remove a skill from the profile.

    Args:
        db: Async database session.
        user_id: The owning user.
        skill_id: The skill to remove.

    Raises:
        NotFoundError: If it does not exist on this user's profile.
    """
    skill = await _owned_skill(db, user_id=user_id, skill_id=skill_id)
    await db.delete(skill)
    await db.commit()


async def suggest_skill_evidence(
    db: AsyncSession, *, user_id: int
) -> tuple[EvidenceSuggestion, ...]:
    """Propose citations for skills the user's own role descriptions already name.

    A proposal, like `extract_from_cv`: nothing is written. The client shows what was
    found and the ordinary `PATCH /profile/skills/{id}` records whatever the user keeps.

    Args:
        db: Async database session.
        user_id: The owning user.

    Returns:
        One entry per skill with roles worth citing. Empty when the profile has no
        unevidenced skills, or nothing in the descriptions to back them.
    """
    profile = await get_or_create_profile(db, user_id=user_id)
    return suggest_evidence(
        tuple(
            SkillFacts(id=s.id, name=s.name, canonical_name=s.canonical_name)
            for s in profile.skills
        ),
        tuple(
            ExperienceFacts(
                id=e.id,
                title=e.title,
                organisation=e.organisation,
                description=e.description,
            )
            for e in profile.experiences
        ),
        already_cited={
            skill.id: frozenset(e.id for e in skill.evidence)
            for skill in profile.skills
        },
    )


async def _resolve_evidence(
    db: AsyncSession, *, user_id: int, experience_ids: list[int]
) -> list[Experience]:
    """Fetch the cited roles, refusing any that are not the user's.

    Args:
        db: Async database session.
        user_id: The owning user.
        experience_ids: The roles cited as evidence.

    Returns:
        The roles, in the order cited.

    Raises:
        ValidationError: If a cited role is not on this user's profile.
    """
    evidence: list[Experience] = []
    for experience_id in experience_ids:
        try:
            evidence.append(
                await _owned_experience(
                    db, user_id=user_id, experience_id=experience_id
                )
            )
        except NotFoundError as exc:
            # A validation failure, not a 404: the bad reference is in the payload.
            raise ValidationError(DEFAULT_ERROR_EVIDENCE_NOT_OWNED) from exc
    return evidence


async def update_skill(
    db: AsyncSession, *, user_id: int, skill_id: int, payload: SkillUpdate
) -> Skill:
    """Amend a skill, including which roles evidence it.

    Closes the loop the profile screen opens: it reports unevidenced skills as the
    thing to fix, and evidence used to be settable only at creation — which the CV
    importer never does.

    Args:
        db: Async database session.
        user_id: The owning user.
        skill_id: The skill to amend.
        payload: The fields to change; omitted fields are left alone. Evidence, when
            given, replaces the existing citations.

    Returns:
        The updated skill with its evidence loaded.

    Raises:
        NotFoundError: If the skill is not on this user's profile.
        ValidationError: If a cited role is not on this user's profile.
        ConflictError: If renaming it collides with a skill already on the profile.
    """
    skill = await _owned_skill(db, user_id=user_id, skill_id=skill_id)
    changes = payload.model_dump(exclude_unset=True)

    if "evidence_experience_ids" in changes:
        skill.evidence = await _resolve_evidence(
            db, user_id=user_id, experience_ids=changes.pop("evidence_experience_ids")
        )
    if "name" in changes:
        skill.canonical_name = canonical(changes["name"])

    for field, value in changes.items():
        setattr(skill, field, value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(DEFAULT_ERROR_SKILL_DUPLICATE) from exc

    result = await db.execute(
        select(Skill).where(Skill.id == skill.id).options(selectinload(Skill.evidence))
    )
    return result.scalar_one()


async def get_or_create_goals(db: AsyncSession, *, user_id: int) -> CareerGoals:
    """Return the user's goals, creating an empty record on first access.

    Same rule as the profile: the client never has to handle "not set yet" as a distinct
    state, and an empty goals record reads correctly as "nothing stated yet".

    Args:
        db: Async database session.
        user_id: The owning user.

    Returns:
        The user's career goals.
    """
    result = await db.execute(select(CareerGoals).where(CareerGoals.user_id == user_id))
    goals = result.scalar_one_or_none()
    if goals is not None:
        return goals

    goals = CareerGoals(user_id=user_id)
    db.add(goals)
    await db.commit()
    await db.refresh(goals)
    return goals


async def replace_goals(
    db: AsyncSession, *, user_id: int, payload: CareerGoalsUpdate
) -> CareerGoals:
    """Replace the user's goals wholesale.

    A replace rather than a merge: the goals form is edited as a whole, so an omitted
    preference means the user cleared it. Merging would make a preference impossible to
    remove without a separate delete.

    Args:
        db: Async database session.
        user_id: The owning user.
        payload: The complete new set of goals.

    Returns:
        The stored goals.
    """
    goals = await get_or_create_goals(db, user_id=user_id)

    goals.target_roles = payload.target_roles
    # Plain strings, so the enum can gain members without a migration.
    goals.work_regimes = [regime.value for regime in payload.work_regimes]
    goals.regime_non_negotiable = payload.regime_non_negotiable
    goals.work_locations = payload.work_locations
    goals.location_non_negotiable = payload.location_non_negotiable
    goals.min_salary = payload.min_salary
    goals.salary_currency = payload.salary_currency
    goals.salary_non_negotiable = payload.salary_non_negotiable

    await db.commit()
    await db.refresh(goals)
    return goals


async def extract_from_cv(
    db: AsyncSession, *, user_id: int, cv_id: int
) -> ExtractedProfile:
    """Read structured records out of one of the user's uploaded CVs.

    Deliberately **read-only**: it returns a proposal and writes nothing. Extraction is
    guesswork on a document whose layout the author never controlled, so the user
    confirms each record through the ordinary create endpoints. A wrong guess then costs
    a rejected suggestion rather than a false claim on a profile that CV generation is
    grounded in.

    Args:
        db: Async database session.
        user_id: The owning user.
        cv_id: The CV to read.

    Returns:
        The extracted proposal, which may be empty when the layout does not survive
        text extraction.

    Raises:
        CVNotFoundError: If the CV does not exist for this user.
    """
    cv = await get_owned_cv(db, cv_id=cv_id, user_id=user_id)
    text = await extract_cv_text(Path(cv.file_path))
    return extract_profile(text)


def _summary_facts(profile: CareerProfile) -> str:
    """Render the profile as the flat fact list the summary prompt may use.

    Facts only, no instructions — those live in the system prompt. Keeping them apart
    is what makes "state nothing that is not below" checkable.

    Args:
        profile: The profile, with its collections loaded.

    Returns:
        The facts, one per line under a heading per section.
    """
    lines: list[str] = []
    if profile.headline:
        lines.append(f"Headline: {profile.headline}")
    if profile.location:
        lines.append(f"Location: {profile.location}")

    if profile.experiences:
        lines.append("\nRoles:")
        for experience in profile.experiences:
            end = experience.end_date
            ended = end.isoformat() if end else "present"
            entry = (
                f"- {experience.title} at {experience.organisation} "
                f"({experience.start_date.isoformat()} to {ended})"
            )
            if experience.description:
                entry += f"\n  {experience.description}"
            lines.append(entry)

    if profile.educations:
        lines.append("\nEducation:")
        for education in profile.educations:
            studied = education.field_of_study
            field = f" in {studied}" if studied else ""
            lines.append(f"- {education.qualification}{field}, {education.institution}")

    if profile.skills:
        # Labelled, not filtered: dropping them would hide the gap the profile shows.
        lines.append("\nSkills:")
        for skill in profile.skills:
            evidenced = "evidenced by a role" if skill.is_evidenced else "not evidenced"
            lines.append(f"- {skill.name} ({evidenced})")

    return "\n".join(lines)


async def generate_summary(
    db: AsyncSession, *, user_id: int, client: LLMClient
) -> ProfileSummaryResponse:
    """Draft a professional summary from the facts already in the profile.

    Like `extract_from_cv`, this **writes nothing** — the draft reaches the profile
    through `PATCH /profile` if the user keeps it.

    Args:
        db: Async database session.
        user_id: The owning user.
        client: The language model client.

    Returns:
        The proposed summary.

    Raises:
        EmptyProfileError: If the profile has no roles and no skills to write from.
        LLMError: If the model is unreachable or its output is unusable.
    """
    profile = await get_or_create_profile(db, user_id=user_id)
    if not profile.experiences and not profile.skills:
        raise EmptyProfileError

    return await complete_validated(
        client,
        system=PROFILE_SUMMARY_SYSTEM_PROMPT,
        user=PROFILE_SUMMARY_USER_PROMPT.format(facts=_summary_facts(profile)),
        schema=ProfileSummaryResponse,
        retry_prompt=PROFILE_SUMMARY_RETRY_PROMPT,
    )
