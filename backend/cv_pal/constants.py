from collections.abc import Set
from enum import StrEnum
from pathlib import Path
from typing import Final

# Storage
DEFAULT_UPLOAD_DIR: Final[Path] = Path("uploads")
DEFAULT_ALLOWED_EXTENSIONS: Final[Set[str]] = frozenset({".pdf", ".docx"})
DEFAULT_MAX_FILE_SIZE: Final[int] = 10 * 1024 * 1024  # 10 MiB
DEFAULT_UPLOAD_CHUNK_SIZE: Final[int] = 1024 * 1024  # 1 MiB

# DOCX is a ZIP container, so it shares the PK signature.
DEFAULT_MAGIC_BYTES: Final[dict[str, bytes]] = {
    ".pdf": b"%PDF-",
    ".docx": b"PK\x03\x04",
}

# Auth
DEFAULT_TOKEN_TYPE: Final[str] = "bearer"  # noqa: S105  # scheme name, not a secret
DEFAULT_JWT_ALGORITHM: Final[str] = "HS256"
# Browser sessions keep both tokens in HttpOnly cookies, out of reach of page script.
# A client opts in with the session header; its presence on every cookie-authenticated
# request is also the CSRF defence, since a cross-origin form cannot set a header.
DEFAULT_TOKEN_TYPE_COOKIE: Final[str] = "cookie"  # noqa: S105  # a mode, not a secret
DEFAULT_SESSION_HEADER: Final[str] = "X-CV-Pal-Session"
DEFAULT_ACCESS_COOKIE: Final[str] = "cv_pal_access"
DEFAULT_REFRESH_COOKIE: Final[str] = "cv_pal_refresh"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES: Final[int] = 30
# Refresh tokens are opaque random strings rather than JWTs: revocation requires a
# database lookup anyway, and an opaque token cannot leak claims if it is exposed.
DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS: Final[int] = 30
DEFAULT_REFRESH_TOKEN_BYTES: Final[int] = 32
# Hex-encoded SHA-256.
DEFAULT_TOKEN_HASH_LENGTH: Final[int] = 64
DEFAULT_MIN_PASSWORD_LENGTH: Final[int] = 12
# A denial-of-service guard. Bytes, not characters, because UTF-8 makes those differ.
DEFAULT_MAX_PASSWORD_BYTES: Final[int] = 1024

# argon2id, at OWASP's second recommended configuration. Raising these later is safe:
# needs_rehash() upgrades hashes on login.
DEFAULT_ARGON2_TIME_COST: Final[int] = 2
DEFAULT_ARGON2_MEMORY_COST_KIB: Final[int] = 19 * 1024
DEFAULT_ARGON2_PARALLELISM: Final[int] = 1
DEFAULT_ARGON2_HASH_LENGTH: Final[int] = 32
DEFAULT_ARGON2_SALT_LENGTH: Final[int] = 16
# Legacy bcrypt hashes are still verified so existing accounts keep working.
DEFAULT_BCRYPT_PREFIXES: Final[tuple[str, ...]] = ("$2a$", "$2b$", "$2x$", "$2y$")
DEFAULT_BCRYPT_MAX_BYTES: Final[int] = 72
# Short fragments of an email match too eagerly to be useful signal.
DEFAULT_MIN_CONTEXT_TOKEN_LENGTH: Final[int] = 4
DEFAULT_APP_NAME_TOKENS: Final[Set[str]] = frozenset({"cvpal", "cv-pal", "cv pal"})

# Rate limiting. Applied per client address on the auth endpoints.
DEFAULT_RATE_LIMIT_REQUESTS: Final[int] = 10
DEFAULT_RATE_LIMIT_WINDOW_SECONDS: Final[float] = 60.0
# Counted for any submitted email, existing or not, so lockout cannot enumerate
# accounts.
DEFAULT_LOCKOUT_THRESHOLD: Final[int] = 5
DEFAULT_LOCKOUT_BASE_SECONDS: Final[float] = 2.0
DEFAULT_LOCKOUT_BACKOFF_CAP_SECONDS: Final[float] = 300.0
# Past this, expired entries are swept: a flood of addresses must not exhaust memory.
DEFAULT_RATE_LIMIT_MAX_TRACKED_KEYS: Final[int] = 10_000

# Deterministic analysis
# Short enough to accept a terse posting, long enough to reject an accidental paste.
DEFAULT_MIN_JOB_DESCRIPTION_LENGTH: Final[int] = 20
DEFAULT_KEYWORD_MIN_LENGTH: Final[int] = 3
DEFAULT_KEYWORD_MAX_PHRASE_WORDS: Final[int] = 3
# A hard requirement counts for more than a nice-to-have when scoring coverage.
DEFAULT_REQUIRED_KEYWORD_WEIGHT: Final[float] = 3.0
DEFAULT_PREFERRED_KEYWORD_WEIGHT: Final[float] = 1.0
# Roughly one page to four pages of prose.
DEFAULT_CV_MIN_WORDS: Final[int] = 200
DEFAULT_CV_MAX_WORDS: Final[int] = 1200
# Mostly short lines is what a multi-column layout looks like once extracted.
DEFAULT_SHORT_LINE_WORDS: Final[int] = 3
DEFAULT_SHORT_LINE_RATIO_LIMIT: Final[float] = 0.5

# Column sizes
DEFAULT_EMAIL_MAX_LENGTH: Final[int] = 320
DEFAULT_NAME_MAX_LENGTH: Final[int] = 255
DEFAULT_FILENAME_MAX_LENGTH: Final[int] = 255
DEFAULT_PATH_MAX_LENGTH: Final[int] = 1024
# ~97 characters today; the headroom avoids a migration when the cost is raised.
DEFAULT_HASHED_PASSWORD_LENGTH: Final[int] = 255
DEFAULT_SUGGESTION_TYPE_MAX_LENGTH: Final[int] = 32
DEFAULT_HEADLINE_MAX_LENGTH: Final[int] = 255
# Generous for a phone number: people write extensions, country codes and spaces.
DEFAULT_PHONE_MAX_LENGTH: Final[int] = 64
DEFAULT_URL_MAX_LENGTH: Final[int] = 512
DEFAULT_ORGANISATION_MAX_LENGTH: Final[int] = 255
DEFAULT_TITLE_MAX_LENGTH: Final[int] = 255
DEFAULT_LOCATION_MAX_LENGTH: Final[int] = 255
DEFAULT_SKILL_NAME_MAX_LENGTH: Final[int] = 128
DEFAULT_SKILL_CATEGORY_MAX_LENGTH: Final[int] = 64

# Career profile
DEFAULT_ERROR_PROFILE_NOT_FOUND: Final[str] = "Career profile not found"
DEFAULT_ERROR_EXPERIENCE_NOT_FOUND: Final[str] = "Experience not found"
DEFAULT_ERROR_SKILL_NOT_FOUND: Final[str] = "Skill not found"
DEFAULT_ERROR_EDUCATION_NOT_FOUND: Final[str] = "Education entry not found"
DEFAULT_ERROR_SKILL_DUPLICATE: Final[str] = "That skill is already on your profile"
DEFAULT_ERROR_END_BEFORE_START: Final[str] = (
    "The end date cannot precede the start date"
)
DEFAULT_ERROR_EVIDENCE_NOT_OWNED: Final[str] = (
    "That experience is not on your profile, so it cannot be cited as evidence"
)

# Tailored CV generation
# A role listing every term it touched reads as keyword stuffing.
DEFAULT_MAX_SURFACED_SKILLS_PER_ROLE: Final[int] = 6
# A gap list exists to be acted on; forty terms is a wall nobody reads.
DEFAULT_MAX_REPORTED_GAPS: Final[int] = 12
# Long enough to name the company and role, short enough to stay a filename.
DEFAULT_DOWNLOAD_NAME_MAX_LENGTH: Final[int] = 80
DEFAULT_DOCX_MEDIA_TYPE: Final[str] = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
DEFAULT_PDF_MEDIA_TYPE: Final[str] = "application/pdf"
# Five words is the usual near-duplicate shingle.
DEFAULT_SHINGLE_WORDS: Final[int] = 5
# How many recent letters a draft is measured against.
DEFAULT_SIMILARITY_CORPUS_SIZE: Final[int] = 20
# Measured: two different letters score 57-64, the same one with the company
# swapped 62, a rewrite 0. Below the band, and a warning rather than a block.
DEFAULT_SIMILARITY_WARN_THRESHOLD: Final[int] = 40
DEFAULT_MAX_COVER_LETTER_LENGTH: Final[int] = 20_000

# Career goals — what the user is looking for, as opposed to what they have done.
DEFAULT_TARGET_ROLE_MAX_LENGTH: Final[int] = 128
DEFAULT_MAX_TARGET_ROLES: Final[int] = 10
DEFAULT_WORK_LOCATION_MAX_LENGTH: Final[int] = 64
DEFAULT_MAX_WORK_LOCATIONS: Final[int] = 15
# Words a posting uses to mean "we do not restrict where you are". A posting saying any
# of these satisfies every user, whatever they listed.
DEFAULT_UNRESTRICTED_LOCATION_TERMS: Final[frozenset[str]] = frozenset(
    {"worldwide", "anywhere", "global", "globally", "international"}
)
# Dropped before comparing, so "Remote" alone reads as "does not say where" rather than
# as a country called Remote.
DEFAULT_LOCATION_NOISE_TERMS: Final[frozenset[str]] = frozenset(
    {
        "remote",
        "hybrid",
        "onsite",
        "office",
        "timezone",
        "timezones",
        "time",
        "zone",
        "zones",
        "only",
        "and",
        "or",
        "the",
        "in",
        "of",
        "at",
        "from",
        "based",
        "preferred",
        "within",
        "region",
        "regions",
        "area",
    }
)
DEFAULT_CURRENCY_CODE_LENGTH: Final[int] = 3
DEFAULT_MAX_SALARY: Final[int] = 100_000_000
DEFAULT_ERROR_REGIME_NON_NEGOTIABLE_EMPTY: Final[str] = (
    "Choose at least one work arrangement before making it a non-negotiable, "
    "or nothing can ever match"
)
DEFAULT_ERROR_SALARY_NON_NEGOTIABLE_EMPTY: Final[str] = (
    "Set a salary floor before making it a non-negotiable"
)
DEFAULT_ERROR_SALARY_NEEDS_CURRENCY: Final[str] = (
    "A salary floor needs a currency, or the number cannot be compared to a posting"
)
DEFAULT_ERROR_DUPLICATE_WORK_REGIMES: Final[str] = (
    "Each work arrangement can appear only once"
)

# LinkedIn. None of the import routes fetches a URL; see docs/linkedin-import.md.
DEFAULT_LINKEDIN_EXTENSIONS: Final[Set[str]] = frozenset({".pdf", ".zip"})
DEFAULT_LINKEDIN_MAGIC_BYTES: Final[dict[str, bytes]] = {
    ".pdf": b"%PDF-",
    ".zip": b"PK\x03\x04",
}
DEFAULT_MIN_LINKEDIN_PASTE_LENGTH: Final[int] = 120
DEFAULT_MAX_LINKEDIN_PASTE_LENGTH: Final[int] = 200_000
# LinkedIn's own guidance, and what recruiter search indexes hardest.
DEFAULT_LINKEDIN_MIN_HEADLINE_WORDS: Final[int] = 4
DEFAULT_LINKEDIN_MIN_ABOUT_WORDS: Final[int] = 40
DEFAULT_LINKEDIN_MIN_SKILLS: Final[int] = 5
DEFAULT_ERROR_LINKEDIN_NOT_FOUND: Final[str] = (
    "No LinkedIn profile imported yet. Import one first — see docs/linkedin-import.md."
)
DEFAULT_ERROR_LINKEDIN_UNREADABLE: Final[str] = (
    "That file could not be read as a LinkedIn profile. A print-to-PDF of your own "
    "profile page works on every account — see docs/linkedin-import.md."
)
DEFAULT_ERROR_LINKEDIN_EXPORT_EMPTY: Final[str] = (
    "That archive has no profile files in it. Request the Profile, Positions, "
    "Education and Skills files, or the full archive."
)
DEFAULT_ERROR_LINKEDIN_NEEDS_INPUT: Final[str] = (
    "Send either a file or pasted text, not neither"
)
DEFAULT_ERROR_LINKEDIN_AMBIGUOUS_INPUT: Final[str] = (
    "Send either a file or pasted text, not both"
)


class ParseabilitySeverity(StrEnum):
    """How much a parseability finding matters."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def penalty(self) -> int:
        """Return the score deduction for a finding at this severity.

        Returns:
            Points subtracted from the parseability score.
        """
        return {"error": 25, "warning": 10, "info": 3}[self.value]


class ProficiencyLevel(StrEnum):
    """Self-assessed command of a skill."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


# Job postings
DEFAULT_COMPANY_MAX_LENGTH: Final[int] = 255
DEFAULT_CONTENT_HASH_LENGTH: Final[int] = 64
DEFAULT_SOURCE_REF_MAX_LENGTH: Final[int] = 255
# Enum values are short; the column only has to hold the longest of them.
DEFAULT_STATUS_MAX_LENGTH: Final[int] = 32
DEFAULT_MIN_POSTING_LENGTH: Final[int] = 50
DEFAULT_MAX_POSTING_LENGTH: Final[int] = 60_000
# A board that has not answered in this long is not going to.
DEFAULT_HTTP_TIMEOUT_SECONDS: Final[float] = 10.0
DEFAULT_ERROR_POSTING_NOT_FOUND: Final[str] = "Job posting not found"
DEFAULT_ERROR_CONNECTION_NOT_FOUND: Final[str] = "Job board connection not found"
DEFAULT_ERROR_APPLICATION_NOT_FOUND: Final[str] = "Application not found"
# Long enough for a real note about a conversation, short enough not to be a document.
DEFAULT_MAX_NOTES_LENGTH: Final[int] = 4_000
DEFAULT_ERROR_APPLICATION_DUPLICATE: Final[str] = (
    "You have already recorded an application for that posting"
)
DEFAULT_ERROR_APPLIED_IN_FUTURE: Final[str] = (
    "An application cannot have been sent in the future"
)
DEFAULT_ERROR_CONNECTION_DUPLICATE: Final[str] = "You are already watching that board"
DEFAULT_ERROR_UNLISTABLE_SOURCE: Final[str] = (
    "Only Greenhouse, Lever and Remotive can be watched. Everything else arrives by "
    "paste."
)
# Remotive accepts `search`, `category` and `limit` and ignores them (verified
# 2026-08-08), so the whole feed is fetched and filtered here.
DEFAULT_REMOTIVE_FEED_URL: Final[str] = "https://remotive.com/api/remote-jobs"
DEFAULT_REMOTIVE_ATTRIBUTION: Final[str] = "Remotive"
# A board token goes straight into an API path, so it is restricted rather than escaped.
DEFAULT_BOARD_IDENTIFIER_PATTERN: Final[str] = r"^[A-Za-z0-9][A-Za-z0-9-]{0,99}$"
DEFAULT_ERROR_JOB_BOARD_UNAVAILABLE: Final[str] = (
    "That job board could not be read just now. Paste the description instead — it "
    "always works."
)
DEFAULT_ERROR_POSTING_DUPLICATE: Final[str] = "You already saved this posting"
DEFAULT_ERROR_UNSUPPORTED_JOB_URL: Final[str] = (
    "That link is not a job board CV Pal can read. Open the posting, copy the "
    "description, and paste it instead — that always works."
)


class JobSource(StrEnum):
    """Where a posting came from.

    Only sanctioned sources are automated. Anything else arrives by paste, which is the
    fallback that cannot break — see PLANNING.md, Phase 7.
    """

    MANUAL = "manual"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    REMOTIVE = "remotive"


class WorkRegime(StrEnum):
    """Where the work happens.

    Held as an *ordered preference* rather than a single choice, because "remote, but
    hybrid is fine" is the common answer and collapsing it to one value throws away the
    part that decides whether a posting is worth showing.
    """

    REMOTE = "remote"
    HYBRID = "hybrid"
    ON_SITE = "on_site"


class ApplicationStatus(StrEnum):
    """Where an application has got to.

    Deliberately few. Every stage a job search actually turns on is here, and each extra
    one is a decision the user has to make on every update — "phone screen" and
    "technical interview" are both `INTERVIEWING`, and splitting them would buy nothing
    the notes field does not already give.

    `NO_REPLY` is not a status: silence is the absence of one, and recording it as a
    state would need something to write it. Time since `applied_at` says it better.
    """

    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


#: Statuses that end an application. Reply rate counts these as an answer either way.
CLOSED_APPLICATION_STATUSES: Final[frozenset[ApplicationStatus]] = frozenset(
    {ApplicationStatus.OFFER, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN}
)

#: Statuses that mean the employer replied. Withdrawing is the user's move, not a reply.
REPLIED_APPLICATION_STATUSES: Final[frozenset[ApplicationStatus]] = frozenset(
    {
        ApplicationStatus.INTERVIEWING,
        ApplicationStatus.OFFER,
        ApplicationStatus.REJECTED,
    }
)

#: Days after which an application with no reply is worth chasing.
DEFAULT_APPLICATION_STALE_DAYS: Final[int] = 14


class EmploymentType(StrEnum):
    """How a role was held, and — the same vocabulary — what a posting is offering.

    One enum for both on purpose: "what contract is this" has the same answers whether
    it is asked of your past or of a vacancy, and two near-identical enums would drift.

    Kept apart from `WorkRegime`, which is a different question: *where* the work
    happens and *what you are engaged as* are independent, and merging them would make
    "remote contract" unsayable. `OTHER` exists because Remotive emits it.
    """

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    FREELANCE = "freelance"
    INTERNSHIP = "internship"
    VOLUNTEER = "volunteer"
    OTHER = "other"


class LLMProvider(StrEnum):
    """Supported LLM backends."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    CUSTOM = "custom"


class LinkedInSource(StrEnum):
    """How a profile snapshot got in.

    Recorded because it changes what the review can honestly claim: a paste has lost its
    section boundaries, so per-section scoring degrades to whole-document scoring, and
    the review has to say so rather than quietly reporting a section as missing when it
    was only unlabelled.
    """

    PDF = "pdf"
    EXPORT = "export"
    PASTE = "paste"

    @property
    def has_sections(self) -> bool:
        """Whether this source preserves section boundaries.

        Returns:
            True when per-section scoring is meaningful.
        """
        return self is not LinkedInSource.PASTE

    @property
    def precision(self) -> int:
        """How exact this route's data is, for resolving a merge.

        The official archive states dates, titles, the full skill list and the role
        descriptions outright. **A profile PDF does not**: LinkedIn's own "Save to PDF"
        caps skills at the top three and omits role descriptions entirely, so importing
        one after an archive must not be allowed to replace the archive's data. A paste
        has lost the section boundaries on top of that.

        Returns:
            A rank, higher being more exact.
        """
        return {"export": 3, "pdf": 2, "paste": 1}[self.value]


class LinkedInSectionStatus(StrEnum):
    """How a single profile section came out of the review."""

    MISSING = "missing"
    THIN = "thin"
    OK = "ok"


class LinkedInIssueKind(StrEnum):
    """A disagreement between the LinkedIn profile and the career profile.

    Both records describe the same career, so where they differ one of them is wrong in
    front of a recruiter who can see both.
    """

    EMPLOYER_ONLY_ON_LINKEDIN = "employer_only_on_linkedin"
    EMPLOYER_ONLY_ON_PROFILE = "employer_only_on_profile"
    TITLE_DIFFERS = "title_differs"
    DATES_DIFFER = "dates_differ"


class SuggestionType(StrEnum):
    """Categories of CV improvement suggestions."""

    CONTENT = "content"
    STRUCTURE = "structure"
    KEYWORDS = "keywords"


# LLM defaults
DEFAULT_LLM_PROVIDER: Final[LLMProvider] = LLMProvider.OPENAI
DEFAULT_LLM_MODEL_OPENAI: Final[str] = "gpt-4o-mini"
DEFAULT_LLM_MODEL_OLLAMA: Final[str] = "llama3"
DEFAULT_LLM_BASE_URL_OLLAMA: Final[str] = "http://localhost:11434/v1"
DEFAULT_LLM_API_KEY_PLACEHOLDER: Final[str] = "ollama"
DEFAULT_ANTHROPIC_MODEL: Final[str] = "claude-sonnet-5"
# Enough for a full set of suggestions; the prompts ask for a bounded list.
DEFAULT_ANTHROPIC_MAX_TOKENS: Final[int] = 8_000
DEFAULT_LLM_TIMEOUT_SECONDS: Final[float] = 120.0
DEFAULT_LLM_MAX_RETRIES: Final[int] = 2
# The availability probe must answer fast: it runs at start-up and behind a UI notice.
DEFAULT_LLM_PROBE_TIMEOUT_SECONDS: Final[float] = 5.0
DEFAULT_LLM_UNREACHABLE: Final[str] = "The model provider could not be reached."
DEFAULT_LLM_MODEL_MISSING: Final[str] = (
    "The model '{model}' is not available from the provider."
)
DEFAULT_SUGGESTION_COUNT: Final[int] = 5

# A ceiling, so a model that writes an essay instead of three sentences is rejected.
DEFAULT_SUMMARY_MAX_LENGTH: Final[int] = 1200

# A CV import proposes skills as chips to click one by one. Past this it is a wall.
DEFAULT_MAX_IMPORTED_SKILLS: Final[int] = 60

DEFAULT_MAX_ROLE_HIGHLIGHTS: Final[int] = 8
DEFAULT_HIGHLIGHT_MAX_LENGTH: Final[int] = 400
DEFAULT_ROLE_CONTEXT_MAX_LENGTH: Final[int] = 4_000

# Error messages
DEFAULT_ERROR_NO_FILENAME: Final[str] = "No filename provided"
DEFAULT_ERROR_FILE_TOO_LARGE: Final[str] = (
    "File too large. Maximum size is {size_mb}MB."
)
DEFAULT_ERROR_FILE_TYPE_NOT_ALLOWED: Final[str] = (
    "File type not allowed. Allowed types: {allowed}"
)
DEFAULT_ERROR_FILE_CONTENT_MISMATCH: Final[str] = (
    "File content does not match its extension"
)
DEFAULT_ERROR_CV_NOT_FOUND: Final[str] = "CV not found"
DEFAULT_ERROR_SUGGESTION_NOT_FOUND: Final[str] = "Suggestion not found"
DEFAULT_ERROR_EMAIL_REGISTERED: Final[str] = "Email already registered"
DEFAULT_ERROR_REGISTRATION_CLOSED: Final[str] = (
    "This instance is not accepting new accounts"
)
DEFAULT_ERROR_INVALID_CREDENTIALS: Final[str] = "Incorrect email or password"
DEFAULT_ERROR_UNAUTHORIZED: Final[str] = "Invalid authentication credentials"
DEFAULT_ERROR_USER_NOT_FOUND: Final[str] = "User not found"
DEFAULT_ERROR_INACTIVE_USER: Final[str] = "Inactive user"
DEFAULT_ERROR_RATE_LIMITED: Final[str] = (
    "Too many attempts. Try again in {retry_after} seconds."
)
DEFAULT_ERROR_INVALID_REFRESH_TOKEN: Final[str] = "Invalid or expired refresh token"  # noqa: S105  # message, not a token
DEFAULT_ERROR_PASSWORD_TOO_SHORT: Final[str] = (
    "Password must be at least {minimum} characters"  # noqa: S105  # not a secret
)
DEFAULT_ERROR_PASSWORD_TOO_LONG: Final[str] = (
    "Password must be at most {maximum} bytes when UTF-8 encoded"  # noqa: S105
)
DEFAULT_ERROR_PASSWORD_COMMON: Final[str] = (
    "Password is too common; choose something less predictable"  # noqa: S105
)
DEFAULT_ERROR_PASSWORD_CONTEXTUAL: Final[str] = (
    "Password must not be based on your email address or the application name"  # noqa: S105
)
DEFAULT_ERROR_UNSUPPORTED_FILE_TYPE: Final[str] = "Unsupported file type: {suffix}"
DEFAULT_ERROR_LLM_INVALID_RESPONSE: Final[str] = (
    "The language model returned a response that could not be parsed"
)
DEFAULT_ERROR_PASSWORD_UNCHANGED: Final[str] = (
    "The new password must be different from the current one"  # noqa: S105  # a message
)
DEFAULT_ERROR_WRONG_PASSWORD: Final[str] = "That is not your current password"  # noqa: S105  # a message, not a credential
DEFAULT_ERROR_PROFILE_TOO_EMPTY: Final[str] = (
    "There is not enough in your profile to summarise yet. Add at least one role, or "
    "import one from a CV, and try again."
)
DEFAULT_ERROR_LLM_UNAVAILABLE: Final[str] = (
    "The language model is unavailable. Check the provider configuration."
)
DEFAULT_ERROR_LOCAL_ONLY_VIOLATION: Final[str] = (
    "local_only is enabled; provider {provider} would send data to a hosted service"
)
DEFAULT_ERROR_LOCAL_ONLY_REMOTE_URL: Final[str] = (
    "local_only is enabled; llm_base_url {base_url} is not on this machine or network"
)
DEFAULT_ERROR_API_KEY_REQUIRED: Final[str] = (
    "llm_api_key is required for provider {provider}"
)
DEFAULT_ERROR_BASE_URL_REQUIRED: Final[str] = (
    "llm_base_url is required for provider {provider}"
)
