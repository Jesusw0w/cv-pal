from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from cv_pal.constants import (
    DEFAULT_API_TOKEN_DISPLAY_CHARS,
    DEFAULT_API_TOKEN_NAME_MAX_LENGTH,
    DEFAULT_APPLICATION_SALARY_MAX_LENGTH,
    DEFAULT_COMPANY_MAX_LENGTH,
    DEFAULT_CONTENT_HASH_LENGTH,
    DEFAULT_EMAIL_MAX_LENGTH,
    DEFAULT_FILENAME_MAX_LENGTH,
    DEFAULT_HASHED_PASSWORD_LENGTH,
    DEFAULT_HEADLINE_MAX_LENGTH,
    DEFAULT_LANGUAGE_NAME_MAX_LENGTH,
    DEFAULT_LEVEL_MAX_LENGTH,
    DEFAULT_LOCATION_MAX_LENGTH,
    DEFAULT_NAME_MAX_LENGTH,
    DEFAULT_ORGANISATION_MAX_LENGTH,
    DEFAULT_PATH_MAX_LENGTH,
    DEFAULT_PHONE_MAX_LENGTH,
    DEFAULT_PLATFORM_NAME_MAX_LENGTH,
    DEFAULT_SKILL_CATEGORY_MAX_LENGTH,
    DEFAULT_SKILL_NAME_MAX_LENGTH,
    DEFAULT_SOURCE_REF_MAX_LENGTH,
    DEFAULT_STATUS_MAX_LENGTH,
    DEFAULT_SUGGESTION_TYPE_MAX_LENGTH,
    DEFAULT_TITLE_MAX_LENGTH,
    DEFAULT_TOKEN_HASH_LENGTH,
    DEFAULT_URL_MAX_LENGTH,
    ApplicationStatus,
    EmploymentType,
    JobSource,
    ProficiencyLevel,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(
        String(DEFAULT_EMAIL_MAX_LENGTH), unique=True, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(DEFAULT_HASHED_PASSWORD_LENGTH))
    full_name: Mapped[str | None] = mapped_column(String(DEFAULT_NAME_MAX_LENGTH))
    is_active: Mapped[bool] = mapped_column(default=True)
    # Carried in every access token; bumping it invalidates all of them at once, so a
    # password change or logout-all does not leave 30-minute tokens working.
    token_version: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    cvs: Mapped[list[CV]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    api_tokens: Mapped[list[ApiToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    career_profile: Mapped[CareerProfile | None] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    career_goals: Mapped[CareerGoals | None] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    cover_letters: Mapped[list[CoverLetter]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    applications: Mapped[list[Application]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    job_platforms: Mapped[list[JobPlatform]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="JobPlatform.name",
    )
    job_postings: Mapped[list[JobPosting]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    job_board_connections: Mapped[list[JobBoardConnection]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    linkedin_profile: Mapped[LinkedInProfile | None] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class LinkedInProfile(Base):
    """A snapshot of the user's LinkedIn profile, as they exported it.

    One per user and replaced wholesale on re-import: this is a *photograph of a
    document*, not a second career record, and keeping several would raise the question
    of which one the review speaks for. The career profile stays the single master
    record — see PLANNING.md, *never fabricate experience*.

    The parsed sections are held as JSON rather than normalised into tables on purpose.
    Nothing generates a CV from this, so the shape only has to survive being read back
    for a review; normalising it would imply a promotion to source-of-truth that the
    product deliberately withholds from a document it did not verify.

    Treated as the sensitive document it is: it is scoped to the user, cascades on
    account deletion, and never leaves the instance.
    """

    __tablename__ = "linkedin_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    # Which of the documented import routes produced this. The review says so, because
    # a paste cannot be scored section by section and must not pretend otherwise.
    source: Mapped[str] = mapped_column(String(DEFAULT_SOURCE_REF_MAX_LENGTH))
    profile_url: Mapped[str | None] = mapped_column(String(DEFAULT_URL_MAX_LENGTH))
    full_name: Mapped[str | None] = mapped_column(String(DEFAULT_NAME_MAX_LENGTH))
    headline: Mapped[str | None] = mapped_column(String(DEFAULT_HEADLINE_MAX_LENGTH))
    about: Mapped[str | None] = mapped_column(Text)
    # Positions, educations and skills as parsed. Structured, but not authoritative.
    positions: Mapped[list[dict[str, str | None]]] = mapped_column(JSON, default=list)
    educations: Mapped[list[dict[str, str | None]]] = mapped_column(JSON, default=list)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    sections_found: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Lets the merge keep the better source per group: "Save to PDF" caps skills at
    # three and drops descriptions, so it must not overwrite a data-export archive.
    field_sources: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    # So the review can be recomputed without a fresh export from LinkedIn.
    raw_text: Mapped[str] = mapped_column(Text, default="")
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="linkedin_profile")


class RefreshToken(Base):
    """A long-lived credential that can be exchanged for a new access token.

    Only the hash is stored. The token itself is high-entropy random data, so a single
    SHA-256 is the right primitive here — unlike a password, it needs no work factor,
    and the lookup happens on every refresh.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(DEFAULT_TOKEN_HASH_LENGTH), unique=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class ApiToken(Base):
    """A personal access token an external agent uses to reach the MCP endpoint.

    Hashed like a refresh token. Unlike one it is long-lived and never rotates, which is
    why it is scoped, always expires, and is revoked by a password change.
    """

    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(DEFAULT_API_TOKEN_NAME_MAX_LENGTH))
    token_hash: Mapped[str] = mapped_column(
        String(DEFAULT_TOKEN_HASH_LENGTH), unique=True, index=True
    )
    #: The first characters after the prefix, so the user can tell tokens apart.
    display_hint: Mapped[str] = mapped_column(String(DEFAULT_API_TOKEN_DISPLAY_CHARS))
    #: Space-separated, as OAuth writes scopes.
    scopes: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="api_tokens")


class CareerProfile(Base):
    """The structured master record a tailored CV is rendered from.

    One per user. Everything the product writes must trace back to a row hanging off
    this profile — that is what makes *never fabricate experience* enforceable rather
    than aspirational.
    """

    __tablename__ = "career_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    headline: Mapped[str | None] = mapped_column(String(DEFAULT_HEADLINE_MAX_LENGTH))
    summary: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(DEFAULT_LOCATION_MAX_LENGTH))
    # Optional, and the parseability check says so — but a CV that cannot carry one
    # fails that check every time it is generated.
    phone: Mapped[str | None] = mapped_column(String(DEFAULT_PHONE_MAX_LENGTH))
    website_url: Mapped[str | None] = mapped_column(String(DEFAULT_URL_MAX_LENGTH))
    # Separate from the website because a CV shows it only for development roles.
    github_url: Mapped[str | None] = mapped_column(String(DEFAULT_URL_MAX_LENGTH))
    # Stored, never fetched — see docs/linkedin-import.md.
    linkedin_url: Mapped[str | None] = mapped_column(String(DEFAULT_URL_MAX_LENGTH))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="career_profile")
    experiences: Mapped[list[Experience]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="Experience.start_date.desc()",
    )
    educations: Mapped[list[Education]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="Education.start_date.desc()",
    )
    skills: Mapped[list[Skill]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="Skill.name",
    )
    languages: Mapped[list[ProfileLanguage]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="ProfileLanguage.id",
    )
    portfolio: Mapped[list[PortfolioItem]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="PortfolioItem.id",
    )


class CareerGoals(Base):
    """What the user is looking for, as opposed to what they have already done.

    One per user, and deliberately separate from `CareerProfile`: the profile is a
    record of the past and changes when the user's history does, while goals change when
    the user changes their mind. Matching reads both, and a score is only explainable if
    it can say which of the two a posting failed against.

    Every preference is paired with a flag saying whether it *filters* or merely
    *scores*. Collapsing that distinction turns a search into one that returns nothing.
    """

    __tablename__ = "career_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    # Free text, not a taxonomy id: the vocabulary is software-specific today, so
    # constraining these would exclude every occupation it does not cover.
    target_roles: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Ordered best-first. JSON rather than a child table because nothing queries across
    # users by regime — matching runs in Python over one user's own row.
    work_regimes: Mapped[list[str]] = mapped_column(JSON, default=list)
    regime_non_negotiable: Mapped[bool] = mapped_column(default=False)

    # Where the user may legally work, in their words — "Portugal", "EU". Matching
    # infers no geography: with no containment data, guessing would hide jobs.
    work_locations: Mapped[list[str]] = mapped_column(JSON, default=list)
    location_non_negotiable: Mapped[bool] = mapped_column(default=False)

    # One per kind of contract, because they are not comparable: a day rate and an
    # annual salary for the same person differ by more than the arithmetic, since a
    # contractor pays for their own holidays, pension and gaps between contracts.
    # Each is `{employment_type, minimum, target, currency, period}`.
    salary_expectations: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, default=list
    )
    salary_non_negotiable: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="career_goals")


class JobBoardConnection(Base):
    """A company board the user wants watched.

    Only Tier A boards can be connected — the ones publishing an unauthenticated JSON
    endpoint for their own listings. There is nothing to store for a paste, and nothing
    safe to store for a site that would have to be scraped.

    ``last_synced_at`` is the whole scheduling story for now: syncing is an endpoint the
    user (or a cron entry, or a systemd timer) triggers. A job queue would mean adding
    Redis to a self-hosted application for one periodic task, which is a dependency the
    deployment story does not currently earn.
    """

    __tablename__ = "job_board_connections"
    __table_args__ = (UniqueConstraint("user_id", "source", "identifier"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[JobSource] = mapped_column(String(DEFAULT_SOURCE_REF_MAX_LENGTH))
    # The board token or company slug, not a URL: it is interpolated into an API path,
    # so it is validated to a safe character set on the way in.
    identifier: Mapped[str] = mapped_column(String(DEFAULT_SOURCE_REF_MAX_LENGTH))
    label: Mapped[str] = mapped_column(String(DEFAULT_COMPANY_MAX_LENGTH))
    # Opt-in: a sync that saves less than the user expected is worse than one that saves
    # too much, because the postings it dropped are not anywhere to be found afterwards.
    filter_by_goals: Mapped[bool] = mapped_column(default=False)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="job_board_connections")


class JobPosting(Base):
    """A role the user is considering, however it arrived.

    Stored per user rather than globally: two people searching the same board have
    different profiles, different goals and different reasons to keep a posting, and a
    shared table would make one user's deletion another user's data loss.

    ``content_hash`` is what collapses the same job posted to several boards, and it is
    unique per user so a re-fetch is idempotent.
    """

    __tablename__ = "job_postings"
    __table_args__ = (UniqueConstraint("user_id", "content_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    source: Mapped[JobSource] = mapped_column(
        String(DEFAULT_SOURCE_REF_MAX_LENGTH), default=JobSource.MANUAL
    )
    source_url: Mapped[str | None] = mapped_column(String(DEFAULT_URL_MAX_LENGTH))
    external_id: Mapped[str | None] = mapped_column(
        String(DEFAULT_SOURCE_REF_MAX_LENGTH)
    )

    title: Mapped[str] = mapped_column(String(DEFAULT_TITLE_MAX_LENGTH))
    company: Mapped[str | None] = mapped_column(String(DEFAULT_COMPANY_MAX_LENGTH))
    location: Mapped[str | None] = mapped_column(String(DEFAULT_LOCATION_MAX_LENGTH))
    description: Mapped[str] = mapped_column(Text)
    # Most sources never say, and "unknown" is not "full time".
    employment_type: Mapped[EmploymentType | None] = mapped_column(
        String(DEFAULT_SOURCE_REF_MAX_LENGTH)
    )

    content_hash: Mapped[str] = mapped_column(String(DEFAULT_CONTENT_HASH_LENGTH))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="job_postings")


class Application(Base):
    """A posting the user actually applied for, and what happened next.

    The last step of the journey, and the one the product could not previously see. Its
    absence was visible on the dashboard: the "funnel" counted saved postings, scored
    matches and uploaded CVs — three numbers that only ever grow and that no application
    passes between.

    ``cv_id`` is what makes reply rate answerable per CV version rather than in
    aggregate, which is the only form of that number anyone can act on. Nullable because
    plenty of applications go out through a form that never took a file, and refusing to
    record those would bias the very statistic it exists to produce.

    One per posting: applying twice to the same role is not two applications, and the
    unique constraint is what stops a double-click becoming a second row.
    """

    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("user_id", "job_posting_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_posting_id: Mapped[int] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), index=True
    )
    # The CV sent, if one was. `SET NULL` rather than cascade: deleting an old CV must
    # not delete the record of having applied with it.
    cv_id: Mapped[int | None] = mapped_column(
        ForeignKey("cvs.id", ondelete="SET NULL"), index=True
    )
    # Where it was sent through, for reply rates per platform. Optional: plenty of
    # applications go straight to a company's own careers page.
    platform_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_platforms.id", ondelete="SET NULL"), index=True
    )
    # What was offered, as written ("€3.1-3.3k/month"): bands come in every shape.
    salary: Mapped[str | None] = mapped_column(
        String(DEFAULT_APPLICATION_SALARY_MAX_LENGTH)
    )
    # What happens next, e.g. "Interview 25 Sep" or "Follow up mid-November".
    next_step: Mapped[str | None] = mapped_column(Text)

    status: Mapped[ApplicationStatus] = mapped_column(
        String(DEFAULT_STATUS_MAX_LENGTH), default=ApplicationStatus.APPLIED
    )
    # When the application went out, which is not when the row was created — people
    # record an application days after sending it, and every interval is measured
    # from this.
    applied_at: Mapped[date]
    # When the status last moved. With `applied_at` this is the whole timeline anyone
    # needs; a per-transition history table can come when something actually reads it.
    status_changed_at: Mapped[date]
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="applications")
    posting: Mapped[JobPosting] = relationship()
    platform: Mapped[JobPlatform | None] = relationship()


class JobPlatform(Base):
    """A job platform the user keeps a profile on — LinkedIn, Indeed, Wellfound.

    Entirely optional. It answers two questions: which platforms still show an older
    version of the profile, and which ones actually produce replies.
    """

    __tablename__ = "job_platforms"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(DEFAULT_PLATFORM_NAME_MAX_LENGTH))
    # Setting a profile up is work in stages; "later" is a decision, not a gap.
    state: Mapped[str] = mapped_column(
        String(DEFAULT_LEVEL_MAX_LENGTH), default="active"
    )
    # The user's own profile page there, when they have one.
    profile_url: Mapped[str | None] = mapped_column(String(DEFAULT_URL_MAX_LENGTH))
    # When the user last brought the platform's copy of their profile up to date. A
    # date the user states, not one observed: nothing here logs in anywhere.
    profile_updated_on: Mapped[date | None]
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="job_platforms")


class CoverLetter(Base):
    """A cover letter the user kept, one per posting.

    Stored for one reason that outweighs the cost of the table: **the self-similarity
    check needs a corpus, and the corpus can only be the user's own letters.** Without
    somewhere to keep them, PLANNING's strongest quality signal — "the last ten letters
    were 92% identical" — cannot be computed at all, and the generator would ship the
    behaviour the project says it exists to prevent.

    Unique per posting, so saving again replaces rather than accumulates drafts: a
    similarity score computed against the user's own earlier attempts at the *same*
    letter would measure nothing.
    """

    __tablename__ = "cover_letters"
    __table_args__ = (UniqueConstraint("user_id", "job_posting_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_posting_id: Mapped[int] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="cover_letters")


class SkillEvidence(Base):
    """Links a skill to the role that demonstrates it.

    The join is the point of the model, not an implementation detail: a skill with no
    evidence is a claim, and the CV generator is expected to treat it differently from
    one backed by a dated role.
    """

    __tablename__ = "skill_evidence"

    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )
    experience_id: Mapped[int] = mapped_column(
        ForeignKey("experiences.id", ondelete="CASCADE"), primary_key=True
    )


class Experience(Base):
    """A role the user has held."""

    __tablename__ = "experiences"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("career_profiles.id", ondelete="CASCADE"), index=True
    )
    organisation: Mapped[str] = mapped_column(String(DEFAULT_ORGANISATION_MAX_LENGTH))
    title: Mapped[str] = mapped_column(String(DEFAULT_TITLE_MAX_LENGTH))
    employment_type: Mapped[EmploymentType | None] = mapped_column(
        String(DEFAULT_SKILL_CATEGORY_MAX_LENGTH)
    )
    location: Mapped[str | None] = mapped_column(String(DEFAULT_LOCATION_MAX_LENGTH))
    # Month precision is what CVs use; the day is conventionally the first.
    start_date: Mapped[date] = mapped_column(Date)
    # Null means "current". A separate boolean could disagree with the dates.
    end_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    profile: Mapped[CareerProfile] = relationship(back_populates="experiences")
    skills: Mapped[list[Skill]] = relationship(
        secondary="skill_evidence", back_populates="evidence"
    )

    @property
    def is_current(self) -> bool:
        """Report whether the role is ongoing.

        Returns:
            True when no end date is recorded.
        """
        return self.end_date is None


class Education(Base):
    """A qualification the user holds or is studying for."""

    __tablename__ = "educations"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("career_profiles.id", ondelete="CASCADE"), index=True
    )
    institution: Mapped[str] = mapped_column(String(DEFAULT_ORGANISATION_MAX_LENGTH))
    qualification: Mapped[str] = mapped_column(String(DEFAULT_TITLE_MAX_LENGTH))
    field_of_study: Mapped[str | None] = mapped_column(String(DEFAULT_TITLE_MAX_LENGTH))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    # Dates are stored whole either way; this says whether the month in them is real.
    date_precision: Mapped[str] = mapped_column(
        String(DEFAULT_LEVEL_MAX_LENGTH), default="month"
    )
    grade: Mapped[str | None] = mapped_column(String(DEFAULT_SKILL_CATEGORY_MAX_LENGTH))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    profile: Mapped[CareerProfile] = relationship(back_populates="educations")


class ProfileLanguage(Base):
    """A language the user speaks, and how well."""

    __tablename__ = "profile_languages"
    __table_args__ = (UniqueConstraint("profile_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("career_profiles.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(DEFAULT_LANGUAGE_NAME_MAX_LENGTH))
    level: Mapped[str] = mapped_column(String(DEFAULT_LEVEL_MAX_LENGTH))

    profile: Mapped[CareerProfile] = relationship(back_populates="languages")


class PortfolioItem(Base):
    """Something the user made that can be shown: a project, a game, a design.

    Deliberately general — a repository and an illustration are both a title, a link
    and a sentence — so the section serves a developer and an artist alike.
    """

    __tablename__ = "portfolio_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("career_profiles.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(DEFAULT_TITLE_MAX_LENGTH))
    url: Mapped[str | None] = mapped_column(String(DEFAULT_URL_MAX_LENGTH))
    description: Mapped[str | None] = mapped_column(Text)

    profile: Mapped[CareerProfile] = relationship(back_populates="portfolio")


class Skill(Base):
    """A capability the user claims, ideally backed by evidence."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("career_profiles.id", ondelete="CASCADE"), index=True
    )
    # The user's spelling, kept for display.
    name: Mapped[str] = mapped_column(String(DEFAULT_SKILL_NAME_MAX_LENGTH))
    # Alias-resolved, so "K8s" and "Kubernetes" deduplicate. See `keywords.canonical`.
    canonical_name: Mapped[str] = mapped_column(
        String(DEFAULT_SKILL_NAME_MAX_LENGTH), index=True
    )
    category: Mapped[str | None] = mapped_column(
        String(DEFAULT_SKILL_CATEGORY_MAX_LENGTH)
    )
    proficiency: Mapped[ProficiencyLevel | None] = mapped_column(
        String(DEFAULT_SKILL_CATEGORY_MAX_LENGTH)
    )
    years: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("profile_id", "canonical_name", name="uq_skill_per_profile"),
    )

    profile: Mapped[CareerProfile] = relationship(back_populates="skills")
    evidence: Mapped[list[Experience]] = relationship(
        secondary="skill_evidence", back_populates="skills"
    )

    @property
    def is_evidenced(self) -> bool:
        """Report whether any role on the profile demonstrates this skill.

        Returns:
            True when at least one experience is cited.
        """
        return bool(self.evidence)


class CV(Base):
    """CV document model."""

    __tablename__ = "cvs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(DEFAULT_FILENAME_MAX_LENGTH))
    file_path: Mapped[str] = mapped_column(String(DEFAULT_PATH_MAX_LENGTH))
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="cvs")
    suggestions: Mapped[list[Suggestion]] = relationship(
        back_populates="cv", cascade="all, delete-orphan"
    )


class Suggestion(Base):
    """AI suggestion for CV improvement."""

    __tablename__ = "suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    cv_id: Mapped[int] = mapped_column(
        ForeignKey("cvs.id", ondelete="CASCADE"), index=True
    )
    suggestion_type: Mapped[str] = mapped_column(
        String(DEFAULT_SUGGESTION_TYPE_MAX_LENGTH)
    )
    content: Mapped[str] = mapped_column(Text)
    accepted: Mapped[bool | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    cv: Mapped[CV] = relationship(back_populates="suggestions")
