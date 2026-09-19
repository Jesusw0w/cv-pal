import { HttpRequest } from '@angular/common/http';

import {
  ApplicationResponse,
  CareerGoalsResponse,
  CareerProfileResponse,
  CvResponse,
  EducationResponse,
  ExperienceResponse,
  JobBoardConnectionResponse,
  JobPostingResponse,
  LinkedInProfileResponse,
  CoverLetterDraftResponse,
  ProfileSummaryResponse,
  ScoredPostingResponse,
  TailoredCvResponse,
  SkillResponse,
  SuggestionResponse,
  TokenResponse,
  UserResponse,
} from '../app/shared/models/api.model';
import {
  MOCK_CAREER_PROFILE,
  MOCK_COVERAGE,
  MOCK_CVS,
  MOCK_EXTRACTION,
  MOCK_GENERATED_SUGGESTIONS,
  MOCK_GOALS,
  MOCK_LINKEDIN_PROFILE,
  MOCK_LINKEDIN_REVIEW,
  MOCK_PARSEABILITY,
  MOCK_SCORED_JOBS,
  MOCK_SUGGESTIONS,
  MOCK_TOKEN,
  MOCK_USER,
} from './fixtures/api.fixtures';

/** A resolved mock response: the status to return and the body to return with it. */
export interface MockResult {
  status: number;
  body: unknown;
  /** Only the file downloads need these, to name the saved file. */
  headers?: Record<string, string>;
}

/** Thrown by a handler to produce an error response with the API's error envelope. */
export class MockHttpError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail);
  }
}

/**
 * In-memory store seeded from the fixtures.
 *
 * Mutations persist for the lifetime of the page, so uploading a CV, analysing it and
 * accepting a suggestion is clickable end to end. A reload resets to the fixtures.
 */
export class MockBackend {
  private cvs: CvResponse[] = [];
  private linkedin: LinkedInProfileResponse | null = null;
  private suggestions: SuggestionResponse[] = [];
  /** Mutable, so renaming the account changes the heading of the CVs the demo renders. */
  private user: UserResponse = MOCK_USER;
  private profile: CareerProfileResponse = MOCK_CAREER_PROFILE;
  private nextProfileChildId = 100;
  private goals: CareerGoalsResponse = MOCK_GOALS;
  private jobs: ScoredPostingResponse[] = [];
  private nextJobId = 100;
  private sources: JobBoardConnectionResponse[] = [];
  private applications: ApplicationResponse[] = [];
  /** Kept letters, so the similarity check has the corpus it needs to mean anything. */
  private letters = new Map<number, string>();
  private nextCvId = 1;
  private nextSuggestionId = 1;
  private tokenCounter = 0;

  constructor() {
    this.reset();
  }

  /** Restore the store to its seeded state. */
  reset(): void {
    this.user = { ...MOCK_USER };
    this.cvs = MOCK_CVS.map((cv) => ({ ...cv }));
    this.linkedin = null;
    this.suggestions = MOCK_SUGGESTIONS.map((s) => ({ ...s }));
    this.profile = structuredClone(MOCK_CAREER_PROFILE);
    this.nextProfileChildId = 100;
    this.goals = structuredClone(MOCK_GOALS);
    this.jobs = MOCK_SCORED_JOBS.map((entry) => structuredClone(entry));
    this.nextJobId = 100;
    this.sources = [];
    this.applications = [];
    this.letters = new Map();
    this.nextCvId = Math.max(0, ...this.cvs.map((c) => c.id)) + 1;
    this.nextSuggestionId = Math.max(0, ...this.suggestions.map((s) => s.id)) + 1;
  }

  /**
   * Resolve a request against the mock routes.
   *
   * @returns The mock result, or `null` when no route matches — the caller turns that
   *   into a 404 so a missing fixture is loud rather than silently hanging.
   */
  handle(request: HttpRequest<unknown>): MockResult | null {
    const path = normalisePath(request.url);
    const { method } = request;

    if (method === 'GET' && (path === '/health' || path === '/health/live')) {
      return { status: 200, body: { status: 'ok' } };
    }

    if (method === 'POST' && path === '/auth/register') {
      return { status: 201, body: this.register(request.body) };
    }

    if (
      method === 'POST' &&
      (path === '/auth/login' || path === '/auth/refresh')
    ) {
      return { status: 200, body: this.issueTokens() };
    }

    if (
      method === 'POST' &&
      (path === '/auth/logout' || path === '/auth/logout-all')
    ) {
      return { status: 204, body: null };
    }

    if (method === 'GET' && path === '/users/me/export') {
      return {
        status: 200,
        body: {
          exported_at: new Date().toISOString(),
          account: this.user,
          profile: this.profile,
          goals: this.goals,
          documents: this.cvs,
          job_postings: this.jobs.map((entry) => entry.posting),
        },
      };
    }

    if (path === '/users/me' && (method === 'GET' || method === 'PATCH')) {
      if (method === 'PATCH') {
        const payload = (request.body ?? {}) as { full_name?: string | null };
        this.user = { ...this.user, full_name: payload.full_name?.trim() || null };
      }
      return { status: 200, body: this.user };
    }

    if (path === '/profile') {
      if (method === 'GET') {
        return { status: 200, body: this.profile };
      }
      if (method === 'PATCH') {
        this.profile = { ...this.profile, ...(request.body as object) };
        return { status: 200, body: this.profile };
      }
    }

    if (path === '/profile/goals') {
      if (method === 'GET') {
        return { status: 200, body: this.goals };
      }
      if (method === 'PUT') {
        // PUT replaces: an omitted preference is cleared, matching the API.
        this.goals = { ...MOCK_GOALS, ...(request.body as object), id: this.goals.id };
        return { status: 200, body: this.goals };
      }
    }

    if (path === '/applications' && (method === 'GET' || method === 'POST')) {
      if (method === 'POST') {
        return { status: 201, body: this.recordApplication(request.body) };
      }
      return { status: 200, body: this.applications.map((a) => this.withAge(a)) };
    }

    if (method === 'GET' && path === '/applications/stats') {
      return { status: 200, body: this.applicationStats() };
    }

    if (method === 'GET' && path === '/applications/unapplied') {
      const applied = new Set(this.applications.map((a) => a.posting.id));
      return {
        status: 200,
        body: this.jobs.map((e) => e.posting).filter((p) => !applied.has(p.id)),
      };
    }

    const applicationId = matchId(path, '/applications');
    if (applicationId !== null && (method === 'PATCH' || method === 'DELETE')) {
      if (method === 'DELETE') {
        this.applications = this.applications.filter((a) => a.id !== applicationId);
        return { status: 204, body: null };
      }
      const payload = (request.body ?? {}) as Partial<ApplicationResponse>;
      const found = this.applications.find((a) => a.id === applicationId);
      if (!found) {
        throw new MockHttpError(404, 'Application not found');
      }
      if (payload.status && payload.status !== found.status) {
        found.status_changed_at = today();
      }
      Object.assign(found, payload);
      return { status: 200, body: this.withAge(found) };
    }

    if (method === 'GET' && path === '/jobs/sources') {
      return { status: 200, body: this.sources };
    }

    if (method === 'POST' && path === '/jobs/sources') {
      const payload = (request.body ?? {}) as Partial<JobBoardConnectionResponse>;
      const created: JobBoardConnectionResponse = {
        id: this.nextJobId++,
        source: payload.source ?? 'greenhouse',
        identifier: payload.identifier ?? 'acme',
        label: payload.label ?? (payload.identifier ?? 'acme'),
        filter_by_goals: payload.filter_by_goals ?? false,
        last_synced_at: null,
        last_error: null,
      };
      this.sources = [...this.sources, created];
      return { status: 201, body: created };
    }

    // Before the parameterised sync, for the same reason the real router declares it
    // first: otherwise `sync` is read as a connection id.
    if (method === 'POST' && path === '/jobs/sources/sync') {
      const now = new Date().toISOString();
      return {
        status: 200,
        body: this.sources.map((source) => {
          source.last_synced_at = now;
          return { connection_id: source.id, found: 2, added: 0, skipped: 0, error: null };
        }),
      };
    }

    const syncId = matchId(path, '/jobs/sources', '/sync');
    if (method === 'POST' && syncId !== null) {
      // Mirrors the real endpoint's idempotence: a board already synced adds nothing.
      const source = this.sources.find((s) => s.id === syncId);
      if (source) {
        source.last_synced_at = new Date().toISOString();
      }
      return {
        status: 200,
        body: { connection_id: syncId, found: 2, added: 0, skipped: 0, error: null },
      };
    }

    const sourceId = matchId(path, '/jobs/sources');
    if (method === 'DELETE' && sourceId !== null) {
      this.sources = this.sources.filter((s) => s.id !== sourceId);
      return { status: 204, body: null };
    }

    if (method === 'GET' && isCollection(path, '/jobs')) {
      return { status: 200, body: this.jobs };
    }

    if (method === 'POST' && path === '/jobs/paste') {
      return { status: 201, body: this.addJob(request.body) };
    }

    if (method === 'POST' && path === '/jobs/import-url') {
      const url = String((request.body as { url?: string } | null)?.url ?? '');
      // Only sanctioned boards resolve, as in the API. Demoing a general URL fetcher
      // would advertise a capability that cannot safely be built.
      if (
        !/(boards|job-boards)\.greenhouse\.io|jobs\.lever\.co|remotive\.com\/remote-jobs\//i.test(
          url,
        )
      ) {
        throw new MockHttpError(
          400,
          'That link is not a job board CV Pal can read. Open the posting, copy the ' +
            'description, and paste it instead — that always works.',
        );
      }
      return { status: 201, body: this.addJob({ title: 'Imported role', description: url }) };
    }

    const letterId = matchId(path, '/jobs', '/cover-letter');
    if (letterId !== null && (method === 'POST' || method === 'PUT')) {
      const edited =
        method === 'PUT'
          ? String((request.body as { body?: string } | null)?.body ?? '')
          : null;
      return { status: 200, body: this.coverLetter(letterId, edited) };
    }

    // Before the plain /tailor route, which these would otherwise fall past into the
    // loud 404 — leaving the download buttons dead in the public-demo build.
    for (const format of ['docx', 'pdf'] as const) {
      const fileId = matchId(path, '/jobs', `/tailor/${format}`);
      if (method === 'POST' && fileId !== null) {
        return this.tailorFile(fileId, format);
      }
    }

    const tailorId = matchId(path, '/jobs', '/tailor');
    if (method === 'POST' && tailorId !== null) {
      return { status: 200, body: this.tailor(tailorId) };
    }

    const jobId = matchId(path, '/jobs');
    if (method === 'DELETE' && jobId !== null) {
      this.jobs = this.jobs.filter((entry) => entry.posting.id !== jobId);
      return { status: 204, body: null };
    }

    const importFromCv = matchId(path, '/profile/import-from-cv');
    if (method === 'POST' && importFromCv !== null) {
      this.requireCv(importFromCv);
      return { status: 200, body: MOCK_EXTRACTION };
    }

    if (method === 'GET' && path === '/profile/skills/evidence-suggestions') {
      return { status: 200, body: this.evidenceSuggestions() };
    }

    if (method === 'POST' && path === '/profile/summary') {
      return { status: 200, body: this.draftSummary() };
    }

    // Any password: the mock has no credential store. Both sign the client out.
    if (method === 'PATCH' && path === '/users/me/password') {
      return { status: 204, body: null };
    }

    if (method === 'DELETE' && path === '/users/me') {
      this.reset();
      return { status: 204, body: null };
    }

    if (method === 'POST' && path === '/profile/experiences') {
      return { status: 201, body: this.addExperience(request.body) };
    }
    if (method === 'POST' && path === '/profile/educations') {
      return { status: 201, body: this.addEducation(request.body) };
    }
    if (method === 'POST' && path === '/profile/skills') {
      return { status: 201, body: this.addSkill(request.body) };
    }

    for (const key of ['experiences', 'educations', 'skills'] as const) {
      const id = matchId(path, `/profile/${key}`);
      if (id === null) {
        continue;
      }
      if (method === 'DELETE') {
        this.profile = {
          ...this.profile,
          [key]: this.profile[key].filter((item) => item.id !== id),
        };
        return { status: 204, body: null };
      }
      if (method === 'PATCH') {
        return { status: 200, body: this.patchProfileChild(key, id, request.body) };
      }
    }

    // LinkedIn. The snapshot starts absent, because "nothing imported yet" is the
    // state a user actually opens this screen in.
    if (path === '/linkedin/review') {
      if (this.linkedin === null) {
        throw new MockHttpError(404, 'No LinkedIn profile imported yet.');
      }
      return { status: 200, body: MOCK_LINKEDIN_REVIEW };
    }
    if (path === '/linkedin/import' && method === 'POST') {
      this.linkedin = { ...MOCK_LINKEDIN_PROFILE };
      return { status: 201, body: this.linkedin };
    }
    if (path === '/linkedin') {
      if (method === 'DELETE') {
        this.linkedin = null;
        return { status: 204, body: null };
      }
      if (this.linkedin === null) {
        throw new MockHttpError(404, 'No LinkedIn profile imported yet.');
      }
      return { status: 200, body: this.linkedin };
    }

    if (method === 'GET' && isCollection(path, '/cvs')) {
      return { status: 200, body: this.listCvs(request) };
    }

    if (method === 'POST' && isCollection(path, '/cvs')) {
      return { status: 201, body: this.createCv(request.body) };
    }

    const cvId = matchId(path, '/cvs');
    if (cvId !== null) {
      if (method === 'GET') {
        return { status: 200, body: this.requireCv(cvId) };
      }
      if (method === 'DELETE') {
        this.deleteCv(cvId);
        return { status: 204, body: null };
      }
    }

    const atsCheckId = matchId(path, '/analysis/cvs', '/ats-check');
    if (method === 'POST' && atsCheckId !== null) {
      this.requireCv(atsCheckId);
      return { status: 200, body: MOCK_PARSEABILITY };
    }

    const coverageId = matchId(path, '/analysis/cvs', '/coverage');
    if (method === 'POST' && coverageId !== null) {
      this.requireCv(coverageId);
      return { status: 200, body: MOCK_COVERAGE };
    }

    const analyseId = matchId(path, '/reviews/cvs', '/analyze');
    if (method === 'POST' && analyseId !== null) {
      return { status: 201, body: this.analyse(analyseId) };
    }

    const suggestionsFor = matchId(path, '/reviews/cvs', '/suggestions');
    if (method === 'GET' && suggestionsFor !== null) {
      this.requireCv(suggestionsFor);
      return {
        status: 200,
        body: this.suggestions.filter((s) => s.cv_id === suggestionsFor),
      };
    }

    const suggestionId = matchId(path, '/reviews/suggestions');
    if (method === 'PATCH' && suggestionId !== null) {
      return { status: 200, body: this.setAccepted(suggestionId, request.body) };
    }

    return null;
  }

  /**
   * Issue a token pair. Each call returns a distinct refresh token, mirroring the
   * backend's rotation so UI code that stores the new one is exercised.
   */
  private issueTokens(): TokenResponse {
    this.tokenCounter += 1;
    return {
      access_token: MOCK_TOKEN,
      refresh_token: `${MOCK_TOKEN}-refresh-${this.tokenCounter}`,
      token_type: 'bearer',
    };
  }

  private register(body: unknown): UserResponse {
    const payload = (body ?? {}) as { email?: string; full_name?: string | null };
    return {
      ...MOCK_USER,
      email: payload.email ?? MOCK_USER.email,
      full_name: payload.full_name ?? null,
    };
  }

  private listCvs(request: HttpRequest<unknown>): CvResponse[] {
    const limit = Number(request.params.get('limit') ?? this.cvs.length);
    const offset = Number(request.params.get('offset') ?? 0);
    return [...this.cvs]
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .slice(offset, offset + limit);
  }

  private createCv(body: unknown): CvResponse {
    const filename =
      body instanceof FormData
        ? ((body.get('file') as File | null)?.name ?? 'uploaded.pdf')
        : 'uploaded.pdf';

    const cv: CvResponse = {
      id: this.nextCvId++,
      user_id: MOCK_USER.id,
      filename,
      version: this.cvs.length + 1,
      created_at: new Date().toISOString(),
    };
    this.cvs = [cv, ...this.cvs];
    return cv;
  }

  /**
   * Add a posting and give it a score.
   *
   * The score is a placeholder: real scoring reads the profile and the goals, which the
   * mock does not model. It is deliberately middling rather than flattering, so the
   * demo does not imply every posting is a great match.
   */
  /**
   * A tailored CV for a saved posting.
   *
   * Built from the seeded profile rather than from a canned string, so the demo shows
   * the real property: every line traces to a profile fact. A fixed document would
   * demonstrate the opposite of what the feature claims.
   */
  /**
   * A drafted summary, assembled from the store rather than canned: what is being
   * demonstrated is that it only contains facts the profile holds. The empty-profile
   * refusal is mirrored because it is the guarantee, not an edge case.
   */
  private draftSummary(): ProfileSummaryResponse {
    const roles = this.profile.experiences;
    if (roles.length === 0 && this.profile.skills.length === 0) {
      throw new MockHttpError(
        400,
        'There is not enough in your profile to summarise yet. Add at least one role, ' +
          'or import one from a CV, and try again.',
      );
    }
    const evidenced = this.profile.skills
      .filter((skill) => skill.is_evidenced)
      .slice(0, 3)
      .map((skill) => skill.name);
    const current = roles[0];
    return {
      summary:
        `${current.title} at ${current.organisation}` +
        (evidenced.length > 0 ? `, working across ${evidenced.join(', ')}.` : '.') +
        ` ${roles.length} role${roles.length > 1 ? 's' : ''} recorded in this profile.`,
    };
  }

  /**
   * The same tailored CV as a downloadable file.
   *
   * Markdown in the blob, and the filename says so: a real DOCX would mean
   * reimplementing `generation/` in TypeScript, and a file Word cannot open would be
   * worse than the 404 this replaces.
   */
  private tailorFile(postingId: number, format: 'docx' | 'pdf'): MockResult {
    const cv = this.tailor(postingId);
    return {
      status: 200,
      body: new Blob([cv.markdown], { type: 'text/markdown' }),
      headers: { 'Content-Disposition': `attachment; filename="CV (${format} demo).md"` },
    };
  }

  private tailor(postingId: number): TailoredCvResponse {
    const posting = this.jobs.find((entry) => entry.posting.id === postingId);
    if (!posting) {
      throw new MockHttpError(404, 'Job posting not found');
    }
    const wanted = posting.posting.description.toLowerCase();
    const surfaced = this.profile.skills
      .filter((skill) => skill.is_evidenced && wanted.includes(skill.canonical_name))
      .map((skill) => ({
        term: skill.canonical_name,
        required: true,
        skill: skill.name,
        evidence: this.profile.experiences
          .slice(0, 1)
          .map((role) => `${role.title}, ${role.organisation}`),
      }));

    const profile = this.profile;
    const markdown = [
      `# ${this.user.full_name ?? 'Curriculum Vitae'}`,
      profile.headline ?? '',
      '',
      [profile.location, this.user.email].filter(Boolean).join(' | '),
      '',
      '## Summary',
      '',
      profile.summary ?? '',
      '',
      '## Skills',
      '',
      profile.skills
        .filter((skill) => skill.is_evidenced)
        .map((skill) => skill.name)
        .join(', '),
      '',
      '## Experience',
      ...profile.experiences.flatMap((role) => [
        '',
        `### ${role.title}, ${role.organisation}`,
        '',
        `${role.start_date.slice(0, 7)} - ${role.end_date?.slice(0, 7) ?? 'Present'}`,
        '',
        role.description ?? '',
      ]),
    ].join('\n');

    return {
      markdown,
      surfaced,
      gaps: posting.match.missing_required.map((term) => ({ term, required: true })),
      // The demo profile spells things the way the postings do, so nothing substitutes.
      substitutions: [],
      omitted_unevidenced: this.profile.skills
        .filter((skill) => !skill.is_evidenced)
        .map((skill) => skill.name),
      parseability: MOCK_PARSEABILITY,
    };
  }

  /**
   * A cover letter draft, and the similarity check that ships with it.
   *
   * The similarity is computed against letters kept *in this session*, so the demo
   * shows the real behaviour: the first letter scores 0, the second scaffolded one
   * scores high, and writing something specific brings it down.
   */
  private coverLetter(
    postingId: number,
    edited: string | null,
  ): CoverLetterDraftResponse {
    const posting = this.jobs.find((entry) => entry.posting.id === postingId);
    if (!posting) {
      throw new MockHttpError(404, 'Job posting not found');
    }
    const evidence = this.profile.skills
      .filter((skill) => skill.is_evidenced)
      .slice(0, 2)
      .map(
        (skill) =>
          `- ${skill.name}: ${this.profile.experiences[0]?.title ?? 'Role'}, ` +
          `${this.profile.experiences[0]?.organisation ?? 'Company'}`,
      );

    const body =
      edited ??
      [
        'Dear Hiring Team,',
        '',
        `I am writing to apply for the role of ${posting.posting.title} at ` +
          `${posting.posting.company ?? 'your company'}.`,
        '',
        this.profile.summary ?? '',
        '',
        'Where your requirements meet my experience:',
        '',
        ...evidence,
        '',
        MOCK_LETTER_PROMPT,
        '',
        'Kind regards,',
        this.user.full_name ?? '',
      ].join('\n');

    const others = [...this.letters.entries()]
      .filter(([id]) => id !== postingId)
      .map(([, text]) => text);
    const similarity = mockSimilarity(body, others);

    if (edited !== null) {
      this.letters.set(postingId, edited);
    }

    return {
      body,
      evidence: edited === null ? evidence : [],
      needs_writing: body.includes(MOCK_LETTER_PROMPT),
      similarity,
      similarity_warning: similarity >= 40,
    };
  }

  private addJob(body: unknown): ScoredPostingResponse {
    const payload = (body ?? {}) as Partial<JobPostingResponse>;
    const entry: ScoredPostingResponse = {
      posting: {
        id: this.nextJobId++,
        source: 'manual',
        source_url: null,
        title: payload.title ?? 'Untitled role',
        company: payload.company ?? null,
        location: payload.location ?? null,
        description: payload.description ?? '',
        // A paste carries no contract type: the form does not ask, and the API does
        // not infer one from the text.
        employment_type: null,
        created_at: new Date().toISOString(),
      },
      match: {
        score: 61,
        blocked_by: null,
        reasons: [
          { label: 'Skills 55/100', detail: 'Scored against your profile by the API.' },
          { label: 'Title 80/100', detail: 'Against the roles you are targeting.' },
          { label: 'Work arrangement', detail: 'The posting does not say.' },
        ],
        missing_required: [],
      },
    };
    this.jobs = [entry, ...this.jobs];
    return entry;
  }

  private addExperience(body: unknown): ExperienceResponse {
    const payload = (body ?? {}) as Partial<ExperienceResponse>;
    const created: ExperienceResponse = {
      id: this.nextProfileChildId++,
      organisation: payload.organisation ?? '',
      title: payload.title ?? '',
      employment_type: payload.employment_type ?? null,
      location: payload.location ?? null,
      start_date: payload.start_date ?? '',
      end_date: payload.end_date ?? null,
      description: payload.description ?? null,
      is_current: !payload.end_date,
    };
    this.profile = {
      ...this.profile,
      experiences: [...this.profile.experiences, created],
    };
    return created;
  }

  private addEducation(body: unknown): EducationResponse {
    const payload = (body ?? {}) as Partial<EducationResponse> & {
      institution?: string;
      qualification?: string;
    };
    const created: EducationResponse = {
      id: this.nextProfileChildId++,
      institution: payload.institution ?? '',
      qualification: payload.qualification ?? '',
      field_of_study: payload.field_of_study ?? null,
      start_date: payload.start_date ?? null,
      end_date: payload.end_date ?? null,
      grade: payload.grade ?? null,
    };
    this.profile = {
      ...this.profile,
      educations: [...this.profile.educations, created],
    };
    return created;
  }

  private addSkill(body: unknown): SkillResponse {
    const payload = (body ?? {}) as Partial<SkillResponse>;
    const evidence = payload.evidence_experience_ids ?? [];
    const created: SkillResponse = {
      id: this.nextProfileChildId++,
      name: payload.name ?? '',
      canonical_name: (payload.name ?? '').toLowerCase(),
      category: payload.category ?? null,
      proficiency: payload.proficiency ?? null,
      years: payload.years ?? null,
      // Mirrors the API: a skill is evidenced only when a role backs it.
      is_evidenced: evidence.length > 0,
      evidence_experience_ids: evidence,
    };
    this.profile = { ...this.profile, skills: [...this.profile.skills, created] };
    return created;
  }

  /** `is_evidenced` is recomputed, since that derivation is what the picker shows. */
  private patchProfileChild(
    key: 'experiences' | 'educations' | 'skills',
    id: number,
    body: unknown,
  ): ExperienceResponse | EducationResponse | SkillResponse {
    const existing = this.profile[key].find((item) => item.id === id);
    if (!existing) {
      throw new MockHttpError(404, 'Not found');
    }
    const updated = { ...existing, ...((body ?? {}) as object) } as typeof existing;
    if (key === 'skills') {
      const skill = updated as SkillResponse;
      skill.is_evidenced = skill.evidence_experience_ids.length > 0;
    }
    this.profile = {
      ...this.profile,
      [key]: this.profile[key].map((item) => (item.id === id ? updated : item)),
    };
    return updated;
  }

  private requireCv(id: number): CvResponse {
    const cv = this.cvs.find((c) => c.id === id);
    if (!cv) {
      throw new MockHttpError(404, 'CV not found');
    }
    return cv;
  }

  /** Record an application against a saved posting. */
  private recordApplication(body: unknown): ApplicationResponse {
    const payload = (body ?? {}) as { job_posting_id?: number; cv_id?: number | null };
    const entry = this.jobs.find((e) => e.posting.id === payload.job_posting_id);
    if (!entry) {
      throw new MockHttpError(404, 'Job posting not found');
    }
    if (this.applications.some((a) => a.posting.id === entry.posting.id)) {
      throw new MockHttpError(400, 'You have already recorded an application for that posting');
    }
    const created: ApplicationResponse = {
      id: this.nextJobId++,
      status: 'applied',
      applied_at: today(),
      status_changed_at: today(),
      cv_id: payload.cv_id ?? null,
      notes: null,
      posting: entry.posting,
      days_since_applied: 0,
      needs_chasing: false,
    };
    this.applications = [created, ...this.applications];
    return created;
  }

  /** Recompute the two fields the real API derives from today's date. */
  private withAge(application: ApplicationResponse): ApplicationResponse {
    const days = Math.floor(
      (Date.now() - new Date(application.applied_at).getTime()) / 86_400_000,
    );
    const open = !['rejected', 'withdrawn'].includes(application.status);
    return { ...application, days_since_applied: days, needs_chasing: open && days > 14 };
  }

  /**
   * The same reply-rate rule as the backend: only applications old enough to have been
   * answered count, so the demo does not show a figure the real API would not.
   */
  private applicationStats(): unknown {
    const all = this.applications.map((a) => this.withAge(a));
    const byStatus: Record<string, number> = {
      applied: 0,
      interviewing: 0,
      offer: 0,
      rejected: 0,
      withdrawn: 0,
    };
    for (const application of all) {
      byStatus[application.status] += 1;
    }
    const replied = all.filter((a) =>
      ['interviewing', 'offer', 'rejected'].includes(a.status),
    ).length;
    const answerable = all.filter(
      (a) => a.days_since_applied > 14 || ['interviewing', 'offer', 'rejected'].includes(a.status),
    ).length;
    return {
      total: all.length,
      by_status: byStatus,
      replied,
      answerable,
      reply_rate: answerable ? Math.round((replied / answerable) * 100) : null,
      needs_chasing: all.filter((a) => a.needs_chasing).length,
    };
  }

  /**
   * The same rule as the backend, at demo scale: a role naming a skill can evidence it.
   *
   * Token comparison rather than substring, so the demo does not show a suggestion the
   * real endpoint would refuse to make.
   */
  private evidenceSuggestions(): unknown[] {
    return this.profile.skills
      .map((skill) => {
        const cited = new Set(skill.evidence_experience_ids);
        const roles = this.profile.experiences.filter((role) => {
          if (cited.has(role.id)) {
            return false;
          }
          const words = `${role.title} ${role.description ?? ''}`
            .toLowerCase()
            .split(/[^a-z0-9+#./-]+/);
          return words.includes(skill.canonical_name.toLowerCase());
        });
        return { skill, roles };
      })
      .filter(({ roles }) => roles.length > 0)
      .map(({ skill, roles }) => ({
        skill_id: skill.id,
        skill_name: skill.name,
        experience_ids: roles.map((role) => role.id),
        experience_labels: roles.map((role) => `${role.title}, ${role.organisation}`),
      }));
  }

  private deleteCv(id: number): void {
    this.requireCv(id);
    this.cvs = this.cvs.filter((c) => c.id !== id);
    this.suggestions = this.suggestions.filter((s) => s.cv_id !== id);
  }

  private analyse(cvId: number): SuggestionResponse[] {
    this.requireCv(cvId);
    const created = MOCK_GENERATED_SUGGESTIONS.map((template) => ({
      ...template,
      id: this.nextSuggestionId++,
      cv_id: cvId,
      created_at: new Date().toISOString(),
    }));
    this.suggestions = [...this.suggestions, ...created];
    return created;
  }

  private setAccepted(id: number, body: unknown): SuggestionResponse {
    const suggestion = this.suggestions.find((s) => s.id === id);
    if (!suggestion) {
      throw new MockHttpError(404, 'Suggestion not found');
    }
    const payload = (body ?? {}) as { accepted?: boolean };
    suggestion.accepted = payload.accepted ?? null;
    return suggestion;
  }
}

/** Strip the origin and any trailing slash so routes can be matched on the path alone. */
function normalisePath(url: string): string {
  const withoutOrigin = url.replace(/^[a-z]+:\/\/[^/]+/i, '');
  const withoutQuery = withoutOrigin.split('?')[0];
  return withoutQuery.length > 1 ? withoutQuery.replace(/\/$/, '') : withoutQuery;
}

/** Match a collection path, tolerating the trailing slash FastAPI uses. */
function isCollection(path: string, base: string): boolean {
  return path === base;
}

/**
 * Extract a numeric id from a path of the form `<base>/<id><suffix>`.
 *
 * @returns The id, or `null` when the path does not match or the id is not numeric.
 */
function matchId(path: string, base: string, suffix = ''): number | null {
  if (!path.startsWith(`${base}/`)) {
    return null;
  }
  const remainder = path.slice(base.length + 1);
  const segment = suffix ? remainder.slice(0, -suffix.length) : remainder;

  if (suffix && !remainder.endsWith(suffix)) {
    return null;
  }
  if (!segment || segment.includes('/')) {
    return null;
  }

  const id = Number(segment);
  return Number.isInteger(id) ? id : null;
}

/** The placeholder the real generator leaves for the paragraph only the user can write. */
const MOCK_LETTER_PROMPT =
  '[Write one paragraph here: why this company, and what about this role you want. ' +
  'Nothing else in this letter is specific to them, and a reader can tell.]';

/**
 * Five-word shingles and Jaccard overlap, mirroring `analysis/similarity.py`.
 *
 * Reimplemented rather than faked: a canned number would demo the opposite of what the
 * check claims, which is that it responds to what the user actually writes.
 */
function mockSimilarity(draft: string, previous: string[]): number {
  if (previous.length === 0) {
    return 0;
  }
  const shingles = (text: string): Set<string> => {
    const words = text.toLowerCase().match(/[a-z0-9']+/g) ?? [];
    if (words.length === 0) {
      return new Set();
    }
    if (words.length <= 5) {
      return new Set([words.join(' ')]);
    }
    return new Set(
      words.slice(0, words.length - 4).map((_, i) => words.slice(i, i + 5).join(' ')),
    );
  };
  const draftShingles = shingles(draft);
  const scores = previous.map((earlier) => {
    const other = shingles(earlier);
    if (draftShingles.size === 0 || other.size === 0) {
      return 0;
    }
    const shared = [...draftShingles].filter((s) => other.has(s)).length;
    return shared / (draftShingles.size + other.size - shared);
  });
  return Math.round(Math.max(...scores) * 100);
}

/** Today, as the API's ISO date. */
function today(): string {
  return new Date().toISOString().slice(0, 10);
}
