from datetime import date, datetime
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from cv_pal.constants import (
    DEFAULT_BOARD_IDENTIFIER_PATTERN,
    DEFAULT_COMPANY_MAX_LENGTH,
    DEFAULT_CURRENCY_CODE_LENGTH,
    DEFAULT_ERROR_APPLIED_IN_FUTURE,
    DEFAULT_ERROR_DUPLICATE_WORK_REGIMES,
    DEFAULT_ERROR_END_BEFORE_START,
    DEFAULT_ERROR_PASSWORD_UNCHANGED,
    DEFAULT_ERROR_REGIME_NON_NEGOTIABLE_EMPTY,
    DEFAULT_ERROR_SALARY_NEEDS_CURRENCY,
    DEFAULT_ERROR_SALARY_NON_NEGOTIABLE_EMPTY,
    DEFAULT_LOCATION_MAX_LENGTH,
    DEFAULT_MAX_COVER_LETTER_LENGTH,
    DEFAULT_MAX_LINKEDIN_PASTE_LENGTH,
    DEFAULT_MAX_NOTES_LENGTH,
    DEFAULT_MAX_POSTING_LENGTH,
    DEFAULT_MAX_SALARY,
    DEFAULT_MAX_TARGET_ROLES,
    DEFAULT_MAX_WORK_LOCATIONS,
    DEFAULT_MIN_JOB_DESCRIPTION_LENGTH,
    DEFAULT_MIN_LINKEDIN_PASTE_LENGTH,
    DEFAULT_MIN_POSTING_LENGTH,
    DEFAULT_NAME_MAX_LENGTH,
    DEFAULT_ORGANISATION_MAX_LENGTH,
    DEFAULT_PHONE_MAX_LENGTH,
    DEFAULT_SKILL_NAME_MAX_LENGTH,
    DEFAULT_SUMMARY_MAX_LENGTH,
    DEFAULT_TARGET_ROLE_MAX_LENGTH,
    DEFAULT_TITLE_MAX_LENGTH,
    DEFAULT_TOKEN_TYPE,
    DEFAULT_URL_MAX_LENGTH,
    DEFAULT_WORK_LOCATION_MAX_LENGTH,
    ApplicationStatus,
    EmploymentType,
    JobSource,
    LinkedInIssueKind,
    LinkedInSectionStatus,
    LinkedInSource,
    ParseabilitySeverity,
    ProficiencyLevel,
    SuggestionType,
    WorkRegime,
)
from cv_pal.passwords import validate_password


class UserCreate(BaseModel):
    """Schema for user registration requests."""

    email: EmailStr
    password: str
    full_name: str | None = None

    @model_validator(mode="after")
    def validate_password_policy(self) -> Self:
        """Enforce the password policy, including checks against the user's own email.

        Runs as a model validator rather than a field validator because rejecting
        context-specific passwords needs the email alongside the password.

        Returns:
            The validated payload.

        Raises:
            ValueError: If the password violates the policy.
        """
        validate_password(self.password, email=self.email)
        return self


class PasswordChange(BaseModel):
    """Change the signed-in account's password.

    The current password is required rather than trusted from the bearer token: a
    stolen access token should not be enough to take the account permanently, which is
    what changing the password would do.
    """

    current_password: str
    new_password: str

    @model_validator(mode="after")
    def validate_password_policy(self) -> Self:
        """Hold the new password to the same policy as registration.

        Returns:
            The validated payload.

        Raises:
            ValueError: If the new password violates the policy, or repeats the old one.
        """
        if self.new_password == self.current_password:
            raise ValueError(DEFAULT_ERROR_PASSWORD_UNCHANGED)
        validate_password(self.new_password)
        return self


class AccountUpdate(BaseModel):
    """Editable fields on the account itself.

    Separate from `CareerProfileUpdate` because the name lives on the user row: it is
    the heading of every generated CV, and until this existed it could only be set at
    registration, where it is optional.
    """

    full_name: str | None = Field(max_length=DEFAULT_NAME_MAX_LENGTH)

    @field_validator("full_name")
    @classmethod
    def blank_is_absent(cls, value: str | None) -> str | None:
        """Treat a cleared field as no name rather than an empty heading.

        Args:
            value: The submitted name.

        Returns:
            The trimmed name, or None when nothing was typed.
        """
        return value.strip() or None if value else None


class AccountDelete(BaseModel):
    """Confirm deletion of the signed-in account.

    Same reasoning as `PasswordChange`, with more at stake: this is not recoverable.
    """

    password: str


class UserResponse(BaseModel):
    """Schema for user data returned in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    """Schema for token responses.

    The refresh token is returned in plaintext exactly once per issue; the server keeps
    only its hash. In a cookie session both are set as HttpOnly cookies instead, and
    the body carries neither — script on the page must never see them.
    """

    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = DEFAULT_TOKEN_TYPE


class RefreshRequest(BaseModel):
    """Schema for exchanging or revoking a refresh token."""

    refresh_token: str = Field(min_length=1)


class CVResponse(BaseModel):
    """Schema for CV data returned in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    filename: str
    version: int
    created_at: datetime


class SuggestionResponse(BaseModel):
    """Schema for AI suggestion data returned in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    cv_id: int
    suggestion_type: str
    content: str
    accepted: bool | None
    created_at: datetime


class SuggestionUpdate(BaseModel):
    """Schema for updating a suggestion's acceptance status."""

    accepted: bool


class KeywordResponse(BaseModel):
    """A term a job description asks for."""

    model_config = ConfigDict(from_attributes=True)

    term: str
    required: bool
    occurrences: int


class CoverageResponse(BaseModel):
    """How well a CV covers a job description."""

    score: int = Field(ge=0, le=100)
    matched: list[KeywordResponse]
    missing: list[KeywordResponse]
    missing_required: list[KeywordResponse]


class CoverageRequest(BaseModel):
    """A job description to compare a CV against."""

    job_description: str = Field(min_length=DEFAULT_MIN_JOB_DESCRIPTION_LENGTH)


class FindingResponse(BaseModel):
    """One machine-readability problem found in a CV."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    severity: ParseabilitySeverity
    message: str


class ParseabilityResponse(BaseModel):
    """Whether an applicant tracking system can read a CV."""

    score: int = Field(ge=0, le=100)
    word_count: int
    findings: list[FindingResponse]
    blocking: list[FindingResponse]


class GeneratedSuggestion(BaseModel):
    """A single suggestion as produced by the language model."""

    type: SuggestionType
    content: str = Field(min_length=1)


class GeneratedSuggestions(BaseModel):
    """Structured-output envelope for a CV analysis response."""

    suggestions: list[GeneratedSuggestion]


class ProfileSummaryResponse(BaseModel):
    """A proposed professional summary.

    Serves twice: it validates what the model returned, and it is the response body.
    Like the CV extraction, this endpoint **writes nothing** — the summary reaches the
    profile only when the user saves it through `PATCH /profile`.
    """

    summary: str = Field(min_length=1, max_length=DEFAULT_SUMMARY_MAX_LENGTH)


class CareerProfileUpdate(BaseModel):
    """Editable fields on the career profile."""

    headline: str | None = None
    summary: str | None = None
    location: str | None = None
    phone: str | None = Field(default=None, max_length=DEFAULT_PHONE_MAX_LENGTH)
    website_url: str | None = None
    linkedin_url: str | None = None


class _DatedEntry(BaseModel):
    """Shared date validation for anything with a start and an end."""

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        """Ensure the end date does not precede the start date.

        Returns:
            The validated payload.

        Raises:
            ValueError: If the dates are the wrong way round.
        """
        start = getattr(self, "start_date", None)
        end = getattr(self, "end_date", None)
        if start is not None and end is not None and end < start:
            raise ValueError(DEFAULT_ERROR_END_BEFORE_START)
        return self


class ExperienceCreate(_DatedEntry):
    """Payload for adding a role to the profile."""

    organisation: str = Field(min_length=1, max_length=DEFAULT_ORGANISATION_MAX_LENGTH)
    title: str = Field(min_length=1, max_length=DEFAULT_TITLE_MAX_LENGTH)
    employment_type: EmploymentType | None = None
    location: str | None = None
    start_date: date
    # Omit to mark the role as current.
    end_date: date | None = None
    description: str | None = None


class ExperienceResponse(BaseModel):
    """A role as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organisation: str
    title: str
    employment_type: EmploymentType | None
    location: str | None
    start_date: date
    end_date: date | None
    description: str | None
    is_current: bool


class ExperienceUpdate(_DatedEntry):
    """Payload for amending a role. Omitted fields are left alone.

    A `PATCH` rather than a `PUT` because these are edited one field at a time — the
    common case is a typo in an employer name, not retyping the row.
    """

    organisation: str | None = Field(
        default=None, min_length=1, max_length=DEFAULT_ORGANISATION_MAX_LENGTH
    )
    title: str | None = Field(
        default=None, min_length=1, max_length=DEFAULT_TITLE_MAX_LENGTH
    )
    employment_type: EmploymentType | None = None
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None


class EducationCreate(_DatedEntry):
    """Payload for adding a qualification to the profile."""

    institution: str = Field(min_length=1, max_length=DEFAULT_ORGANISATION_MAX_LENGTH)
    qualification: str = Field(min_length=1, max_length=DEFAULT_TITLE_MAX_LENGTH)
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    grade: str | None = None


class EducationResponse(BaseModel):
    """A qualification as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    institution: str
    qualification: str
    field_of_study: str | None
    start_date: date | None
    end_date: date | None
    grade: str | None


class EducationUpdate(_DatedEntry):
    """Payload for amending a qualification. Omitted fields are left alone."""

    institution: str | None = Field(
        default=None, min_length=1, max_length=DEFAULT_ORGANISATION_MAX_LENGTH
    )
    qualification: str | None = Field(
        default=None, min_length=1, max_length=DEFAULT_TITLE_MAX_LENGTH
    )
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    grade: str | None = None


class SkillCreate(BaseModel):
    """Payload for adding a skill to the profile."""

    name: str = Field(min_length=1, max_length=DEFAULT_SKILL_NAME_MAX_LENGTH)
    category: str | None = None
    proficiency: ProficiencyLevel | None = None
    years: float | None = Field(default=None, ge=0, le=80)
    # Empty leaves the skill unevidenced, which the CV generator refuses to claim.
    evidence_experience_ids: list[int] = Field(default_factory=list)


class SkillUpdate(BaseModel):
    """Payload for amending a skill. Omitted fields are left alone.

    `evidence_experience_ids` is the exception: when present it **replaces** the
    citations, since removing one is as ordinary an edit as adding one and there is no
    other way to express it.
    """

    name: str | None = Field(
        default=None, min_length=1, max_length=DEFAULT_SKILL_NAME_MAX_LENGTH
    )
    category: str | None = None
    proficiency: ProficiencyLevel | None = None
    years: float | None = Field(default=None, ge=0, le=80)
    evidence_experience_ids: list[int] | None = None


class SkillResponse(BaseModel):
    """A skill as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    canonical_name: str
    category: str | None
    proficiency: ProficiencyLevel | None
    years: float | None
    is_evidenced: bool
    evidence_experience_ids: list[int]


class CareerProfileResponse(BaseModel):
    """The whole profile, as the editor and the CV generator consume it."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    headline: str | None
    summary: str | None
    location: str | None
    phone: str | None
    website_url: str | None
    linkedin_url: str | None
    experiences: list[ExperienceResponse]
    educations: list[EducationResponse]
    skills: list[SkillResponse]


class EvidenceSuggestionResponse(BaseModel):
    """Roles that name a skill the profile does not yet cite for it.

    A proposal, like the CV extraction: the citation reaches the profile only through
    `PATCH /profile/skills/{id}`, which the user triggers.
    """

    skill_id: int
    skill_name: str
    experience_ids: list[int]
    # Named, not just referenced: a list of ids is not something anyone can confirm.
    experience_labels: list[str]


class CareerGoalsUpdate(BaseModel):
    """What the user is looking for.

    A `PUT` body: this replaces the record rather than merging into it, so an omitted
    field is an instruction to clear that preference, not to leave it alone. That is the
    right default for a form the user edits as a whole.
    """

    target_roles: list[str] = Field(
        default_factory=list, max_length=DEFAULT_MAX_TARGET_ROLES
    )
    work_regimes: list[WorkRegime] = Field(default_factory=list)
    regime_non_negotiable: bool = False
    work_locations: list[str] = Field(
        default_factory=list, max_length=DEFAULT_MAX_WORK_LOCATIONS
    )
    location_non_negotiable: bool = False
    min_salary: int | None = Field(default=None, ge=0, le=DEFAULT_MAX_SALARY)
    salary_currency: str | None = Field(
        default=None,
        min_length=DEFAULT_CURRENCY_CODE_LENGTH,
        max_length=DEFAULT_CURRENCY_CODE_LENGTH,
    )
    salary_non_negotiable: bool = False

    @field_validator("target_roles")
    @classmethod
    def clean_roles(cls, roles: list[str]) -> list[str]:
        """Trim the roles and drop the blanks a form will send.

        Args:
            roles: The submitted role titles.

        Returns:
            Non-empty, trimmed, de-duplicated titles in the order given.

        Raises:
            ValueError: If a title is longer than the column allows.
        """
        cleaned: list[str] = []
        for role in roles:
            title = " ".join(role.split())
            if not title:
                continue
            if len(title) > DEFAULT_TARGET_ROLE_MAX_LENGTH:
                raise ValueError(
                    f"Role titles must be {DEFAULT_TARGET_ROLE_MAX_LENGTH} "
                    "characters or fewer"
                )
            if title not in cleaned:
                cleaned.append(title)
        return cleaned

    @field_validator("work_locations")
    @classmethod
    def clean_locations(cls, locations: list[str]) -> list[str]:
        """Trim the places and drop the blanks a form will send.

        Case is preserved rather than normalised: these are shown back to the user as
        they typed them, and matching casefolds its own comparisons.

        Args:
            locations: The submitted places.

        Returns:
            Non-empty, trimmed, de-duplicated places in the order given.

        Raises:
            ValueError: If a place is longer than the column allows.
        """
        cleaned: list[str] = []
        for location in locations:
            place = " ".join(location.split())
            if not place:
                continue
            if len(place) > DEFAULT_WORK_LOCATION_MAX_LENGTH:
                raise ValueError(
                    f"Places must be {DEFAULT_WORK_LOCATION_MAX_LENGTH} "
                    "characters or fewer"
                )
            if place.casefold() not in {done.casefold() for done in cleaned}:
                cleaned.append(place)
        return cleaned

    @field_validator("salary_currency")
    @classmethod
    def normalise_currency(cls, currency: str | None) -> str | None:
        """Upper-case the currency so "eur" and "EUR" are the same floor.

        Args:
            currency: The submitted ISO 4217 code, or ``None``.

        Returns:
            The upper-cased code, or ``None``.
        """
        return currency.upper() if currency is not None else None

    @model_validator(mode="after")
    def validate_goals(self) -> Self:
        """Reject combinations that could never match anything.

        A non-negotiable with nothing behind it is not a strict search, it is an empty
        one — it filters out every posting and gives the user no way to see why. Better
        to refuse it at the edge than to explain a permanently empty result list.

        Returns:
            The validated payload.

        Raises:
            ValueError: If a non-negotiable has no value, if a salary floor has no
                currency, or if a work arrangement is listed twice.
        """
        if len(set(self.work_regimes)) != len(self.work_regimes):
            raise ValueError(DEFAULT_ERROR_DUPLICATE_WORK_REGIMES)
        if self.regime_non_negotiable and not self.work_regimes:
            raise ValueError(DEFAULT_ERROR_REGIME_NON_NEGOTIABLE_EMPTY)
        if self.salary_non_negotiable and self.min_salary is None:
            raise ValueError(DEFAULT_ERROR_SALARY_NON_NEGOTIABLE_EMPTY)
        if self.min_salary is not None and self.salary_currency is None:
            raise ValueError(DEFAULT_ERROR_SALARY_NEEDS_CURRENCY)
        return self


class CareerGoalsResponse(BaseModel):
    """The user's goals, as matching and the goals form consume them."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    target_roles: list[str]
    work_regimes: list[WorkRegime]
    regime_non_negotiable: bool
    work_locations: list[str]
    location_non_negotiable: bool
    min_salary: int | None
    salary_currency: str | None
    salary_non_negotiable: bool


class ExtractedContactResponse(BaseModel):
    """Contact details found in an uploaded CV."""

    model_config = ConfigDict(from_attributes=True)

    email: str | None
    phone: str | None
    linkedin_url: str | None
    website_url: str | None


class ExtractedEntryResponse(BaseModel):
    """A dated entry read from an uploaded CV. A proposal, not a stored record."""

    model_config = ConfigDict(from_attributes=True)

    organisation: str
    title: str
    location: str | None
    start_date: date | None
    end_date: date | None
    description: str | None


class CvExtractionResponse(BaseModel):
    """What a deterministic pass over an uploaded CV could find.

    Nothing here is persisted. The client shows it for confirmation and creates the
    records the user keeps through the ordinary profile endpoints — which is what keeps
    *never fabricate experience* true of a parser that is necessarily guessing.
    """

    model_config = ConfigDict(from_attributes=True)

    contact: ExtractedContactResponse
    # The three fields the wizard used to ask the user to type out while the CV in front
    # of it already said them.
    headline: str | None
    summary: str | None
    location: str | None
    experiences: list[ExtractedEntryResponse]
    educations: list[ExtractedEntryResponse]
    skills: list[str]


class JobPostingCreate(BaseModel):
    """A posting the user pasted. The route that always works."""

    title: str = Field(min_length=1, max_length=DEFAULT_TITLE_MAX_LENGTH)
    company: str | None = Field(default=None, max_length=DEFAULT_COMPANY_MAX_LENGTH)
    location: str | None = Field(default=None, max_length=DEFAULT_LOCATION_MAX_LENGTH)
    description: str = Field(
        min_length=DEFAULT_MIN_POSTING_LENGTH, max_length=DEFAULT_MAX_POSTING_LENGTH
    )
    source_url: str | None = Field(default=None, max_length=DEFAULT_URL_MAX_LENGTH)


class JobPostingImport(BaseModel):
    """A link to a posting on a job board CV Pal can read."""

    url: str = Field(min_length=1, max_length=DEFAULT_URL_MAX_LENGTH)


class JobPostingResponse(BaseModel):
    """A saved posting."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source: JobSource
    source_url: str | None
    title: str
    company: str | None
    location: str | None
    description: str
    # None means the source did not say; the interface shows nothing, not "full time".
    employment_type: EmploymentType | None
    created_at: datetime


class MatchReasonResponse(BaseModel):
    """One component of a match score, phrased for display."""

    model_config = ConfigDict(from_attributes=True)

    label: str
    detail: str


class MatchScoreResponse(BaseModel):
    """Why a posting scored what it did.

    Every score is explainable: `reasons` is what the number is made of, and
    `blocked_by` names the non-negotiable a posting broke rather than silently ranking
    it low.
    """

    model_config = ConfigDict(from_attributes=True)

    score: int = Field(ge=0, le=100)
    blocked_by: str | None
    reasons: list[MatchReasonResponse]
    missing_required: list[str]


class ScoredPostingResponse(BaseModel):
    """A posting with its score."""

    posting: JobPostingResponse
    match: MatchScoreResponse


class JobBoardConnectionCreate(BaseModel):
    """A company board to watch."""

    source: JobSource
    # Interpolated into a board API path, so restricted rather than escaped.
    identifier: str = Field(pattern=DEFAULT_BOARD_IDENTIFIER_PATTERN)
    label: str | None = Field(default=None, max_length=DEFAULT_COMPANY_MAX_LENGTH)
    # Off unless asked for: a sync that saves less than expected hides postings the user
    # has no other way to find.
    filter_by_goals: bool = False


class JobBoardConnectionResponse(BaseModel):
    """A watched board."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source: JobSource
    identifier: str
    label: str
    filter_by_goals: bool
    last_synced_at: datetime | None
    last_error: str | None


class SyncResultResponse(BaseModel):
    """What one board sync did."""

    model_config = ConfigDict(from_attributes=True)

    connection_id: int
    found: int
    added: int
    skipped: int
    error: str | None


class ApplicationCreate(BaseModel):
    """Record that an application went out."""

    job_posting_id: int
    # The CV that was sent, when one was. Optional because plenty of applications go
    # through a form that never took a file, and refusing those would bias the reply
    # rate this table exists to compute.
    cv_id: int | None = None
    # Defaults to today rather than being required: the overwhelmingly common case is
    # recording an application as it is sent.
    applied_at: date | None = None
    notes: str | None = Field(default=None, max_length=DEFAULT_MAX_NOTES_LENGTH)

    @field_validator("applied_at")
    @classmethod
    def not_in_the_future(cls, value: date | None) -> date | None:
        """Reject a date that has not happened.

        Args:
            value: The submitted date.

        Returns:
            The date, unchanged.

        Raises:
            ValueError: If it is in the future, which would make every interval
                measured from it negative.
        """
        if value is not None and value > date.today():
            raise ValueError(DEFAULT_ERROR_APPLIED_IN_FUTURE)
        return value


class ApplicationUpdate(BaseModel):
    """Move an application along, or amend what was recorded."""

    status: ApplicationStatus | None = None
    cv_id: int | None = None
    applied_at: date | None = None
    notes: str | None = Field(default=None, max_length=DEFAULT_MAX_NOTES_LENGTH)


class ApplicationResponse(BaseModel):
    """An application and the posting it was for."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ApplicationStatus
    applied_at: date
    status_changed_at: date
    cv_id: int | None
    notes: str | None
    posting: JobPostingResponse
    #: Days since it went out. Computed rather than stored — it changes without anything
    #: writing to the row, and a stored copy would be wrong by morning.
    days_since_applied: int
    #: True when it has been long enough with no reply to be worth chasing.
    needs_chasing: bool


class ApplicationStatsResponse(BaseModel):
    """How the search is actually going.

    Reply rate is the one number a job seeker can act on, and it is only meaningful
    against applications old enough to have been answered — counting yesterday's as
    unanswered would make every active search look like a failing one.
    """

    total: int
    #: Counts per status, so the funnel can be drawn without a second request.
    by_status: dict[ApplicationStatus, int]
    replied: int
    #: Sent long enough ago to expect an answer. The reply-rate denominator.
    answerable: int
    reply_rate: int | None
    needs_chasing: int


class SurfacedFactResponse(BaseModel):
    """A profile fact brought forward because the posting asked for it."""

    model_config = ConfigDict(from_attributes=True)

    term: str
    required: bool
    skill: str
    evidence: list[str]


class GapResponse(BaseModel):
    """Something the posting wants that the profile cannot evidence.

    Reported, never written into the document — the boundary the three permitted
    transforms draw.
    """

    model_config = ConfigDict(from_attributes=True)

    term: str
    required: bool


class SubstitutionResponse(BaseModel):
    """A word taken from the posting in place of the user's, for the same thing.

    Reported per use because it is the only text in the document that is not literally
    the user's own — see `generation.tailored_cv.substitute` for why it is safe.
    """

    model_config = ConfigDict(from_attributes=True)

    from_term: str
    to_term: str
    via: str


class TailoredCvResponse(BaseModel):
    """A CV rendered for one posting, with the reasoning that produced it.

    The explanation is not decoration: every element of it is what lets the user check
    that nothing was invented, which is the claim the whole feature rests on.
    """

    model_config = ConfigDict(from_attributes=True)

    markdown: str
    surfaced: list[SurfacedFactResponse]
    gaps: list[GapResponse]
    omitted_unevidenced: list[str]
    substitutions: list[SubstitutionResponse]
    # The generated document run through the checks an uploaded one gets, so a
    # generator its own analyser would flag cannot ship quietly.
    parseability: ParseabilityResponse


class CoverLetterDraftResponse(BaseModel):
    """A letter assembled from profile facts, with what it is measured against.

    `similarity` travels with the draft rather than being a separate call, because a
    generator that could be used without seeing the number would be the product doing
    the thing it says it is against.
    """

    body: str
    evidence: list[str]
    # True while the placeholder survives — the one paragraph only the user can write.
    needs_writing: bool
    similarity: int = Field(ge=0, le=100)
    # Warned, never blocked — see `DEFAULT_SIMILARITY_WARN_THRESHOLD`.
    similarity_warning: bool


class CoverLetterSave(BaseModel):
    """A letter to keep against a posting, as edited."""

    body: str = Field(min_length=1, max_length=DEFAULT_MAX_COVER_LETTER_LENGTH)


class LinkedInImportRequest(BaseModel):
    """A LinkedIn profile pasted as text.

    The route that is always available: no export to request, no menu item that may not
    be there. It loses the section boundaries, which is why the review reports which
    mode produced it rather than scoring absent sections as missing.
    """

    text: str = Field(
        min_length=DEFAULT_MIN_LINKEDIN_PASTE_LENGTH,
        max_length=DEFAULT_MAX_LINKEDIN_PASTE_LENGTH,
    )


class LinkedInProfileResponse(BaseModel):
    """The imported snapshot, as parsed.

    A record of a document the user exported — never a second source of truth. Nothing
    generates a CV from this; the career profile remains the master record.
    """

    model_config = ConfigDict(from_attributes=True)

    source: LinkedInSource
    profile_url: str | None
    full_name: str | None
    headline: str | None
    about: str | None
    positions: list[ExtractedEntryResponse]
    educations: list[ExtractedEntryResponse]
    skills: list[str]
    sections_found: list[str]
    # So the screen can show what a further import would actually add.
    field_sources: dict[str, str]
    imported_at: datetime


class LinkedInSectionResponse(BaseModel):
    """One section's verdict."""

    model_config = ConfigDict(from_attributes=True)

    section: str
    status: LinkedInSectionStatus
    detail: str


class LinkedInIssueResponse(BaseModel):
    """One disagreement between LinkedIn and the career profile."""

    model_config = ConfigDict(from_attributes=True)

    kind: LinkedInIssueKind
    organisation: str
    detail: str


class LinkedInReviewResponse(BaseModel):
    """The review of an imported profile.

    Reported, never applied: which of two disagreeing records is right is the user's
    call, and CV Pal has not verified either.
    """

    model_config = ConfigDict(from_attributes=True)

    score: int = Field(ge=0, le=100)
    source: LinkedInSource
    note: str
    sections: list[LinkedInSectionResponse]
    consistency: list[LinkedInIssueResponse]
    # None without target roles: nothing to measure recruiter-search coverage against.
    coverage: CoverageResponse | None
