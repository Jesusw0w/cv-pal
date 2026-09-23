"""The account itself: changing its password, and removing it entirely.

Both re-check the password despite the caller being authenticated. A bearer token proves
a session was opened by the account holder once; it does not prove they are the one
holding it now, and these are the two actions where that difference matters.
"""

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cv_pal import storage
from cv_pal.constants import DEFAULT_ERROR_WRONG_PASSWORD
from cv_pal.exceptions import AuthenticationError
from cv_pal.hashing import hash_password, verify_password
from cv_pal.models import CV, Application, CareerProfile, Skill, User
from cv_pal.services.api_token_service import revoke_all_tokens
from cv_pal.services.auth_service import revoke_all_sessions


def _require_password(user: User, password: str) -> None:
    """Check the account's own password before a credential-level change.

    Args:
        user: The authenticated account.
        password: The password submitted with the request.

    Raises:
        AuthenticationError: If the password does not match.
    """
    if not verify_password(password, user.hashed_password):
        raise AuthenticationError(DEFAULT_ERROR_WRONG_PASSWORD)


async def update_account(
    db: AsyncSession, *, user: User, full_name: str | None
) -> User:
    """Change the account's display name.

    No password check, unlike the two below: the name is not a credential, and every
    generated CV is headed with it, so correcting a typo should not cost a re-auth.

    Args:
        db: Async database session.
        user: The authenticated account.
        full_name: The new name, or None to clear it.

    Returns:
        The updated account.
    """
    user.full_name = full_name
    await db.commit()
    await db.refresh(user)
    return user


async def change_password(
    db: AsyncSession, *, user: User, current_password: str, new_password: str
) -> None:
    """Replace the account's password and end every session.

    Ending the sessions is the point: one that leaves the thief's refresh token working
    has changed a string and nothing else. The caller's own session goes too, and so do
    the agents' access tokens — a password change is what someone does when they think
    the account is compromised.

    Args:
        db: Async database session.
        user: The authenticated account.
        current_password: The password being replaced, as proof of identity.
        new_password: The replacement, already checked against the policy by the schema.

    Raises:
        AuthenticationError: If the current password is wrong.
    """
    _require_password(user, current_password)

    user.hashed_password = hash_password(new_password)
    await revoke_all_tokens(db, user_id=user.id)
    await db.commit()
    await revoke_all_sessions(db, user_id=user.id)


def _account_query(user_id: int) -> Select[tuple[User]]:
    """Select an account with everything hanging off it loaded.

    Shared by the export and the delete so the two cannot disagree about what an account
    consists of — a relationship added here reaches both, and an export that misses what
    the delete destroys would be the worst kind of quiet failure.

    Args:
        user_id: The account to load.

    Returns:
        The statement, with every collection eagerly loaded.
    """
    return (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.cvs).selectinload(CV.suggestions),
            selectinload(User.refresh_tokens),
            selectinload(User.api_tokens),
            selectinload(User.career_profile).selectinload(CareerProfile.experiences),
            selectinload(User.career_profile).selectinload(CareerProfile.educations),
            selectinload(User.career_profile)
            .selectinload(CareerProfile.skills)
            .selectinload(Skill.evidence),
            selectinload(User.career_goals),
            selectinload(User.cover_letters),
            selectinload(User.applications).selectinload(Application.posting),
            selectinload(User.applications).selectinload(Application.platform),
            selectinload(User.job_platforms),
            selectinload(User.job_postings),
            selectinload(User.job_board_connections),
            selectinload(User.linkedin_profile),
        )
    )


def _rows(instances: Iterable[object], *fields: str) -> list[dict[str, Any]]:
    """Copy named columns off ORM rows.

    Args:
        instances: The rows to read.
        *fields: Column names to copy.

    Returns:
        One plain dictionary per row, in the order given.
    """
    return [{name: getattr(row, name) for name in fields} for row in instances]


async def export_account(db: AsyncSession, *, user: User) -> dict[str, Any]:
    """Assemble everything the account holds, for the user to take away.

    Principle 4 says the user owns their data. A hard delete honours half of that; a
    user who cannot get a copy out first only has the half that loses it.

    Loads exactly what `delete_account` loads, and deliberately so: the export is only
    honest if it covers everything the delete would destroy, and one shared list is what
    keeps the two from drifting apart. Uploaded files themselves are not inlined — they
    are downloaded whole from the documents screen.

    Returns:
        A JSON-serialisable snapshot of the account.
    """
    loaded = await db.execute(_account_query(user.id))
    account = loaded.scalar_one()
    profile = account.career_profile
    goals = account.career_goals

    return {
        "exported_at": datetime.now(UTC),
        "account": {
            "email": account.email,
            "full_name": account.full_name,
            "created_at": account.created_at,
        },
        "profile": None
        if profile is None
        else {
            "headline": profile.headline,
            "summary": profile.summary,
            "location": profile.location,
            "phone": profile.phone,
            "website_url": profile.website_url,
            "github_url": profile.github_url,
            "linkedin_url": profile.linkedin_url,
            "experiences": _rows(
                profile.experiences,
                "organisation",
                "title",
                "employment_type",
                "location",
                "start_date",
                "end_date",
                "description",
            ),
            "educations": _rows(
                profile.educations,
                "institution",
                "qualification",
                "field_of_study",
                "start_date",
                "end_date",
                "grade",
            ),
            "skills": [
                {
                    "name": skill.name,
                    "canonical_name": skill.canonical_name,
                    "category": skill.category,
                    "proficiency": skill.proficiency,
                    "years": skill.years,
                    # By title rather than by id: an id means nothing outside this
                    # database, and the export has to be readable on its own.
                    "evidenced_by": [
                        f"{e.title}, {e.organisation}" for e in skill.evidence
                    ],
                }
                for skill in profile.skills
            ],
        },
        "goals": None
        if goals is None
        else {
            "target_roles": list(goals.target_roles),
            "work_regimes": list(goals.work_regimes),
            "regime_non_negotiable": goals.regime_non_negotiable,
            "work_locations": list(goals.work_locations),
            "location_non_negotiable": goals.location_non_negotiable,
            "salary_expectations": list(goals.salary_expectations),
            "salary_non_negotiable": goals.salary_non_negotiable,
        },
        "documents": [
            {
                "filename": cv.filename,
                "version": cv.version,
                "created_at": cv.created_at,
                "suggestions": _rows(
                    cv.suggestions,
                    "suggestion_type",
                    "content",
                    "accepted",
                    "created_at",
                ),
            }
            for cv in account.cvs
        ],
        "job_postings": _rows(
            account.job_postings,
            "source",
            "source_url",
            "title",
            "company",
            "location",
            "description",
            "employment_type",
            "created_at",
        ),
        "cover_letters": _rows(
            account.cover_letters, "job_posting_id", "body", "created_at", "updated_at"
        ),
        "applications": [
            {
                # By title rather than by posting id, for the same reason the skill
                # evidence is: an id means nothing once the export leaves here.
                "posting": f"{application.posting.title}"
                f" at {application.posting.company or 'an unnamed company'}",
                "status": application.status,
                "applied_at": application.applied_at,
                "status_changed_at": application.status_changed_at,
                "platform": application.platform.name if application.platform else None,
                "notes": application.notes,
            }
            for application in account.applications
        ],
        "job_platforms": _rows(
            account.job_platforms, "name", "profile_url", "profile_updated_on", "notes"
        ),
        "job_board_connections": _rows(
            account.job_board_connections, "source", "identifier", "label"
        ),
        "linkedin_profile": None
        if account.linkedin_profile is None
        else {
            "profile_url": account.linkedin_profile.profile_url,
            "full_name": account.linkedin_profile.full_name,
            "headline": account.linkedin_profile.headline,
            "about": account.linkedin_profile.about,
            "positions": account.linkedin_profile.positions,
            "educations": account.linkedin_profile.educations,
            "skills": account.linkedin_profile.skills,
            "imported_at": account.linkedin_profile.imported_at,
        },
    }


async def delete_account(db: AsyncSession, *, user: User, password: str) -> None:
    """Delete the account and everything hanging off it, files included.

    No soft delete: principle 4 says the user owns the data, and an account only marked
    deleted is one the operator still holds.

    The collections are loaded first because the ORM relationships are what cascade —
    SQLite does not enforce foreign keys unless asked, so the schema's `ondelete` is
    documentation here rather than behaviour.

    Args:
        db: Async database session.
        user: The authenticated account.
        password: The account's password, as confirmation.

    Raises:
        AuthenticationError: If the password is wrong.
    """
    _require_password(user, password)

    # Read the paths before the rows go: after the delete there is nothing left to ask.
    stored = await db.execute(select(CV.file_path).where(CV.user_id == user.id))
    files = [Path(path) for path in stored.scalars().all()]

    loaded = await db.execute(_account_query(user.id))
    await db.delete(loaded.scalar_one())
    await db.commit()

    # The row is the source of truth, so the file goes last: a leftover file is
    # recoverable, a row pointing at a deleted one is not.
    for path in files:
        await storage.delete_file(path)
