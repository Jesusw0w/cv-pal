/**
 * Wire contracts for the CV Pal backend.
 *
 * These mirror the Pydantic response schemas in `backend/cv_pal/schemas.py`. Keeping
 * them in one place means the mock fixtures are type-checked against the same shapes
 * the real services consume — a backend contract change that breaks the fixtures fails
 * the build rather than surfacing at runtime.
 */

export interface UserResponse {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  /** Null in a cookie session: the tokens arrive as HttpOnly cookies instead. */
  access_token: string | null;
  /** Single-use. Exchanging it at `/auth/refresh` returns a new pair. */
  refresh_token: string | null;
  /** `cookie` in a cookie session, `bearer` otherwise. */
  token_type: string;
}

/** A personal access token for an agent, as listed. The secret is never included. */
export interface ApiTokenResponse {
  id: number;
  name: string;
  /** The first characters of the secret, to tell tokens apart. */
  display_hint: string;
  /**
   * Space-separated: `cvpal:read`, plus `cvpal:write` when it may record postings and
   * applications, and `cvpal:profile` when it may edit the profile and goals.
   */
  scopes: string;
  expires_at: string;
  last_used_at: string | null;
  created_at: string;
}

/** A token as issued: `token` is shown this once and cannot be recovered. */
export interface ApiTokenCreatedResponse extends ApiTokenResponse {
  token: string;
}

export interface ApiTokenListResponse {
  /** Whether this instance accepts agent connections at all (`CV_PAL_MCP_ENABLED`). */
  mcp_enabled: boolean;
  tokens: ApiTokenResponse[];
}

export interface ApiTokenCreate {
  name: string;
  password: string;
  write: boolean;
  /** Lets the agent add, change and delete profile entries and replace the goals. */
  edit_profile: boolean;
  expires_in_days: number;
}

/** Whether the configured language model can be used. */
export interface LlmStatusResponse {
  status: 'ok' | 'unavailable';
  model: string;
  /** What is wrong, phrased for a person, when unavailable. */
  detail: string | null;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface CvResponse {
  id: number;
  user_id: number;
  filename: string;
  version: number;
  created_at: string;
}

export type SuggestionKind = 'content' | 'structure' | 'keywords';

export interface SuggestionResponse {
  id: number;
  cv_id: number;
  suggestion_type: SuggestionKind;
  content: string;
  accepted: boolean | null;
  created_at: string;
}

/** The error envelope every failing endpoint returns. */
export interface ApiError {
  detail: string;
}

// --- Deterministic analysis. No language model is involved in any of these. ---

export interface KeywordResponse {
  term: string;
  /** True when the posting states it as a hard requirement. */
  required: boolean;
  occurrences: number;
}

export interface CoverageResponse {
  /** Weighted coverage, 0–100. */
  score: number;
  matched: KeywordResponse[];
  missing: KeywordResponse[];
  /** The subset of `missing` the posting marked as required. */
  missing_required: KeywordResponse[];
}

export type FindingSeverity = 'error' | 'warning' | 'info';

export interface FindingResponse {
  /** Stable identifier — safe to branch on for tailored UI copy. */
  code: string;
  severity: FindingSeverity;
  message: string;
}

export interface ParseabilityResponse {
  score: number;
  word_count: number;
  findings: FindingResponse[];
  /** Findings likely to get the CV rejected before a human reads it. */
  blocking: FindingResponse[];
}

// --- Career profile: the master record every generated CV is rendered from. ---

/**
 * How a role was held, and — the same vocabulary — what a posting is offering.
 *
 * One type for both: the question has the same answers whether asked of your past or
 * of a vacancy. `other` exists because Remotive emits it.
 */
export type EmploymentType =
  'full_time' | 'part_time' | 'contract' | 'freelance' | 'internship' | 'volunteer' | 'other';

export type ProficiencyLevel = 'beginner' | 'intermediate' | 'advanced' | 'expert';

export interface ExperienceResponse {
  id: number;
  organisation: string;
  title: string;
  employment_type: EmploymentType | null;
  location: string | null;
  /** ISO calendar date, `YYYY-MM-DD`. */
  start_date: string;
  /** Null means the role is current. There is no separate flag that could disagree. */
  end_date: string | null;
  description: string | null;
  is_current: boolean;
}

export interface EducationResponse {
  id: number;
  institution: string;
  qualification: string;
  field_of_study: string | null;
  start_date: string | null;
  end_date: string | null;
  grade: string | null;
}

export interface SkillResponse {
  id: number;
  name: string;
  /** Deduplication key — "K8s" and "Kubernetes" collapse to one canonical form. */
  canonical_name: string;
  category: string | null;
  proficiency: ProficiencyLevel | null;
  years: number | null;
  /**
   * True when at least one dated role backs the claim. This is what lets a generator
   * tell a grounded claim from an asserted one, so *never fabricate experience* can be
   * enforced rather than hoped for.
   */
  is_evidenced: boolean;
  evidence_experience_ids: number[];
}

export interface CareerProfileResponse {
  id: number;
  headline: string | null;
  summary: string | null;
  location: string | null;
  phone: string | null;
  website_url: string | null;
  /** Put on a generated CV only for development roles; LinkedIn always is. */
  github_url: string | null;
  linkedin_url: string | null;
  experiences: ExperienceResponse[];
  educations: EducationResponse[];
  skills: SkillResponse[];
}

// --- Request bodies. Mirror the Pydantic *Create/*Update models. ---

/** `PATCH /profile`. Omitted fields are left alone; null clears one. */
export interface CareerProfileUpdate {
  headline?: string | null;
  summary?: string | null;
  location?: string | null;
  phone?: string | null;
  website_url?: string | null;
  github_url?: string | null;
  linkedin_url?: string | null;
}

export interface ExperienceCreate {
  organisation: string;
  title: string;
  employment_type?: EmploymentType | null;
  location?: string | null;
  /** ISO `YYYY-MM-DD`. */
  start_date: string;
  /** Omit or null for a current role — there is no separate flag. */
  end_date?: string | null;
  description?: string | null;
}

export interface EducationCreate {
  institution: string;
  qualification: string;
  field_of_study?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  grade?: string | null;
}

export interface SkillCreate {
  name: string;
  category?: string | null;
  proficiency?: ProficiencyLevel | null;
  years?: number | null;
  /** Roles that demonstrate this skill. Empty means the claim is unevidenced. */
  evidence_experience_ids?: number[];
}

/** PATCH bodies. Omitted fields are left alone. */
export type ExperienceUpdate = Partial<ExperienceCreate>;
export type EducationUpdate = Partial<EducationCreate>;

export interface SkillUpdate {
  name?: string;
  category?: string | null;
  proficiency?: ProficiencyLevel | null;
  years?: number | null;
  /** Sent, this replaces the citations rather than adding to them. */
  evidence_experience_ids?: number[];
}

// --- CV extraction. A proposal: none of this is stored until the user confirms. ---

export interface ExtractedContactResponse {
  email: string | null;
  /** Read from the header only, so a date range is not proposed as a phone number. */
  phone: string | null;
  linkedin_url: string | null;
  website_url: string | null;
  github_url: string | null;
}

/** A dated entry read from a CV. Dates may be null when the layout hid them. */
export interface ExtractedEntryResponse {
  organisation: string;
  title: string;
  location: string | null;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
}

export interface CvExtractionResponse {
  contact: ExtractedContactResponse;
  /** The title line under the name, when the header survived text extraction. */
  headline: string | null;
  /** The opening paragraph, when the CV labelled one. */
  summary: string | null;
  location: string | null;
  experiences: ExtractedEntryResponse[];
  educations: ExtractedEntryResponse[];
  skills: string[];
}

/**
 * Roles that name a skill the profile does not yet cite for it.
 *
 * A proposal, like the CV extraction: nothing is written until the user applies it.
 */
export interface EvidenceSuggestionResponse {
  skill_id: number;
  skill_name: string;
  experience_ids: number[];
  /** "Title, Organisation" per role — ids are not something anyone can confirm. */
  experience_labels: string[];
}

/** A drafted summary. A proposal: it is saved through `PATCH /profile`, or discarded. */
export interface ProfileSummaryResponse {
  summary: string;
}

/** What the user remembers about one role, as the notes a draft is written from. */
export interface RoleHighlightsRequest {
  context: string;
}

/**
 * Drafted bullet points for one role.
 *
 * A proposal: they are saved through `PATCH /profile/experiences/{id}`, or discarded.
 * Stored as one bullet per line, which is what the editor shows and what a job board's
 * "describe this role" box expects pasted in.
 */
export interface RoleHighlightsResponse {
  highlights: string[];
}

// --- Career goals: what the user is looking for, as opposed to what they have done. ---

export type WorkRegime = 'remote' | 'hybrid' | 'on_site';

export interface CareerGoalsResponse {
  id: number;
  target_roles: string[];
  /** Ordered best-first — the order is the preference. */
  work_regimes: WorkRegime[];
  regime_non_negotiable: boolean;
  /**
   * Places the user can work from, in their own words.
   *
   * Free text rather than a taxonomy: matching compares these against the wording a
   * posting uses and infers no geography, so listing "Portugal" alone does not match a
   * posting that says "Europe". The goals screen explains this and offers the common
   * regional wordings.
   */
  work_locations: string[];
  location_non_negotiable: boolean;
  /** One per contract type and period — an annual salary and a day rate side by side. */
  salary_expectations: SalaryExpectation[];
  salary_non_negotiable: boolean;
}

/** What a salary figure is per. Contract work is quoted by the day or the hour. */
export type SalaryPeriod = 'year' | 'month' | 'day' | 'hour';

/** What the user wants for one kind of contract. */
export interface SalaryExpectation {
  employment_type: EmploymentType;
  /** The floor. */
  minimum: number;
  /** What they are aiming for, above the floor. */
  target: number | null;
  /** ISO 4217, upper case. */
  currency: string;
  period: SalaryPeriod;
}

/** `PUT /profile/goals` replaces the record: an omitted preference is cleared. */
export type CareerGoalsUpdate = Omit<CareerGoalsResponse, 'id'>;

// --- Job postings and their match scores. ---

export type JobSource = 'manual' | 'greenhouse' | 'lever' | 'remotive';

export interface JobPostingResponse {
  id: number;
  source: JobSource;
  source_url: string | null;
  title: string;
  company: string | null;
  location: string | null;
  description: string;
  /**
   * Null when the source does not state one, which is every Greenhouse and Lever
   * posting — neither exposes it as a field. Show nothing rather than assuming
   * full time.
   */
  employment_type: EmploymentType | null;
  created_at: string;
}

export interface MatchReasonResponse {
  label: string;
  detail: string;
}

export interface MatchScoreResponse {
  score: number;
  /** Set when a non-negotiable was broken — the posting is filtered, not just ranked low. */
  blocked_by: string | null;
  reasons: MatchReasonResponse[];
  missing_required: string[];
  /**
   * Sorts before the score. 0 offers the user's first-choice work arrangement, 1 their
   * second; then postings that do not say; then ones offering none the user chose.
   */
  preference_rank: number;
}

export interface ScoredPostingResponse {
  posting: JobPostingResponse;
  match: MatchScoreResponse;
}

/** A profile fact the posting pulled forward, with what backs it. */
export interface SurfacedFactResponse {
  /** The posting's own term. */
  term: string;
  required: boolean;
  /** The user's spelling of the matching skill — what appears in the document. */
  skill: string;
  /** Roles demonstrating it, as "Title, Organisation". */
  evidence: string[];
}

/** Something the posting wants that no role evidences. Named, never written in. */
export interface GapResponse {
  term: string;
  required: boolean;
}

/** A word taken from the posting in place of the user's, for the same thing. */
export interface SubstitutionResponse {
  /** The user's own spelling, as stored on the profile. */
  from_term: string;
  /** The posting's spelling, used in the document. */
  to_term: string;
  /** The canonical form the alias map resolved both to. */
  via: string;
}

export interface TailoredCvResponse {
  markdown: string;
  surfaced: SurfacedFactResponse[];
  gaps: GapResponse[];
  /** Skills left out because no role demonstrates them. */
  omitted_unevidenced: string[];
  /**
   * Every word in the document that is not literally the user's own.
   *
   * Only fires where the alias map asserts two spellings name one thing, which is also
   * why it never fires outside software — see the backend's `substitute`.
   */
  substitutions: SubstitutionResponse[];
  /** The generated document run through the same checks an uploaded one gets. */
  parseability: ParseabilityResponse;
}

/** A cover letter assembled from profile facts, with the check that keeps it honest. */
export interface CoverLetterDraftResponse {
  body: string;
  /** Requirement-to-role lines, so each claim shows what it rests on. */
  evidence: string[];
  /** True while the one paragraph only the user can write is still a placeholder. */
  needs_writing: boolean;
  /** How much this repeats the user's own kept letters, 0-100. */
  similarity: number;
  /** Warned, never blocked — the user may have a good reason. */
  similarity_warning: boolean;
}

export interface JobPostingCreate {
  title: string;
  company?: string | null;
  location?: string | null;
  description: string;
  source_url?: string | null;
}

/**
 * A source being watched. Greenhouse and Lever hold a company slug; Remotive holds one
 * of its category slugs, because it is a feed of the whole remote market rather than
 * one employer's board.
 */
export interface JobBoardConnectionResponse {
  id: number;
  source: JobSource;
  identifier: string;
  label: string;
  /** When true, a sync saves only postings whose title matches a target role. */
  filter_by_goals: boolean;
  last_synced_at: string | null;
  last_error: string | null;
}

export interface SyncResultResponse {
  connection_id: number;
  found: number;
  added: number;
  /** Turned away by the goal filter. Reported so the filter is visible, not silent. */
  skipped: number;
  error: string | null;
}

// --- Applications: the last step of the journey, and the only list that shrinks. ---

/**
 * Where an application has got to.
 *
 * There is no "no reply" — silence is the absence of a status, and time since
 * `applied_at` says it better than a state nothing would ever write.
 */
export type ApplicationStatus = 'applied' | 'interviewing' | 'offer' | 'rejected' | 'withdrawn';

export interface ApplicationResponse {
  id: number;
  status: ApplicationStatus;
  /** ISO `YYYY-MM-DD`. When it was sent, which is not when the row was created. */
  applied_at: string;
  status_changed_at: string;
  /** The CV that was sent, when one was. Null once that CV is deleted. */
  cv_id: number | null;
  /** The platform it went through, when recorded. */
  platform_id: number | null;
  notes: string | null;
  posting: JobPostingResponse;
  /** Computed server-side: a stored copy would be wrong by morning. */
  days_since_applied: number;
  needs_chasing: boolean;
}

export interface ApplicationCreate {
  job_posting_id: number;
  cv_id?: number | null;
  platform_id?: number | null;
  /** Omit for today, which is the overwhelmingly common case. */
  applied_at?: string | null;
  notes?: string | null;
}

export type ApplicationUpdate = Partial<Omit<ApplicationCreate, 'job_posting_id'>> & {
  status?: ApplicationStatus;
};

export interface ApplicationStatsResponse {
  total: number;
  by_status: Record<ApplicationStatus, number>;
  replied: number;
  /** Sent long enough ago to expect an answer. The reply-rate denominator. */
  answerable: number;
  /** Null until something is answerable — not the same as nobody having replied. */
  reply_rate: number | null;
  needs_chasing: number;
  /** The same figures per platform, best reply rate first; "Not recorded" last. */
  by_platform: PlatformStats[];
}

export interface PlatformStats {
  /** Null for applications recorded without a platform. */
  platform_id: number | null;
  name: string;
  total: number;
  replied: number;
  answerable: number;
  reply_rate: number | null;
  interviews: number;
  offers: number;
}

// --- Job platforms the user keeps a profile on. Entirely optional. ---

/** Whether a platform's copy of the profile is behind the profile in CV Pal. */
export type PlatformStatus = 'up_to_date' | 'outdated' | 'unknown';

export interface JobPlatformResponse {
  id: number;
  name: string;
  profile_url: string | null;
  /** ISO `YYYY-MM-DD`: when the user last brought their profile there up to date. */
  profile_updated_on: string | null;
  notes: string | null;
  status: PlatformStatus;
}

export interface JobPlatformCreate {
  name: string;
  profile_url?: string | null;
  profile_updated_on?: string | null;
  notes?: string | null;
}

export type JobPlatformUpdate = Partial<JobPlatformCreate>;

// --- LinkedIn: the profile the user exported themselves. ---
// CV Pal never fetches linkedin.com — automated access is against LinkedIn's terms and
// the account it would endanger is the user's own. See docs/linkedin-import.md.

/** Which of the documented import routes a snapshot, or a field group, came from. */
export type LinkedInSource = 'pdf' | 'export' | 'paste';

export interface LinkedInProfileResponse {
  source: LinkedInSource;
  profile_url: string | null;
  full_name: string | null;
  headline: string | null;
  about: string | null;
  positions: ExtractedEntryResponse[];
  educations: ExtractedEntryResponse[];
  skills: string[];
  sections_found: string[];
  /**
   * Which route supplied each field group.
   *
   * LinkedIn's own PDF carries only the top three skills and no role descriptions, so
   * this is what lets the screen say what a data export would still add.
   */
  field_sources: Record<string, LinkedInSource>;
  imported_at: string;
}

export type LinkedInSectionStatus = 'missing' | 'thin' | 'ok';

export interface LinkedInSectionResponse {
  /** Stable key — safe to branch on. */
  section: string;
  status: LinkedInSectionStatus;
  detail: string;
}

export type LinkedInIssueKind =
  'employer_only_on_linkedin' | 'employer_only_on_profile' | 'title_differs' | 'dates_differ';

export interface LinkedInIssueResponse {
  kind: LinkedInIssueKind;
  organisation: string;
  detail: string;
}

export interface LinkedInReviewResponse {
  score: number;
  source: LinkedInSource;
  /** What this review could not judge, given the route the snapshot arrived by. */
  note: string;
  sections: LinkedInSectionResponse[];
  consistency: LinkedInIssueResponse[];
  /** Null until the user has named target roles to measure search coverage against. */
  coverage: CoverageResponse | null;
}
