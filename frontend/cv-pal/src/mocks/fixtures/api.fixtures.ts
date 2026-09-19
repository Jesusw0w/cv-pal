import {
  CareerGoalsResponse,
  CareerProfileResponse,
  CoverageResponse,
  CvExtractionResponse,
  LinkedInProfileResponse,
  LinkedInReviewResponse,
  CvResponse,
  ParseabilityResponse,
  ScoredPostingResponse,
  SuggestionResponse,
  UserResponse,
} from '../../app/shared/models/api.model';

/**
 * Seed data for mock mode, typed against the real backend contract.
 *
 * Edit these to change what the UI shows in `npm run start:mock`. Because they are
 * typed as the response models, a backend schema change that is reflected in
 * `api.model.ts` will fail the build here rather than silently drift.
 */

export const MOCK_USER: UserResponse = {
  id: 1,
  email: 'dev@cvpal.test',
  full_name: 'Dev User',
  is_active: true,
  created_at: '2026-01-15T10:00:00Z',
};

export const MOCK_TOKEN = 'mock-access-token';

export const MOCK_CVS: readonly CvResponse[] = [
  {
    id: 1,
    user_id: 1,
    filename: 'software-engineer-cv.pdf',
    version: 3,
    created_at: '2026-07-20T14:30:00Z',
  },
  {
    id: 2,
    user_id: 1,
    filename: 'frontend-developer-cv.pdf',
    version: 2,
    created_at: '2026-06-18T09:00:00Z',
  },
  {
    id: 3,
    user_id: 1,
    filename: 'product-manager-cv.docx',
    version: 1,
    created_at: '2026-03-01T10:00:00Z',
  },
];

export const MOCK_SUGGESTIONS: readonly SuggestionResponse[] = [
  {
    id: 1,
    cv_id: 1,
    suggestion_type: 'content',
    content:
      'Quantify the AngularJS to Angular migration: state the number of screens moved and the resulting change in bundle size.',
    accepted: null,
    created_at: '2026-07-20T14:35:00Z',
  },
  {
    id: 2,
    cv_id: 1,
    suggestion_type: 'structure',
    content:
      'Move the Skills section above Education — recruiters scanning for stack keywords stop reading around two thirds of a page.',
    accepted: true,
    created_at: '2026-07-20T14:35:00Z',
  },
  {
    id: 3,
    cv_id: 1,
    suggestion_type: 'keywords',
    content:
      'You describe container orchestration work but never write "Kubernetes". ATS keyword matching is literal — surface the term explicitly.',
    accepted: false,
    created_at: '2026-07-20T14:35:00Z',
  },
  {
    id: 4,
    cv_id: 2,
    suggestion_type: 'content',
    content:
      'The design system bullet says "2M+ users" without saying what you did. Lead with the action, then the scale.',
    accepted: null,
    created_at: '2026-06-18T09:05:00Z',
  },
];

/** Suggestions returned when a CV with no prior analysis is analysed in mock mode. */
export const MOCK_GENERATED_SUGGESTIONS: readonly Omit<
  SuggestionResponse,
  'id' | 'cv_id' | 'created_at'
>[] = [
  {
    suggestion_type: 'content',
    content:
      'Lead each bullet with an action verb and close it with a measurable result.',
    accepted: null,
  },
  {
    suggestion_type: 'structure',
    content: 'The CV runs to three pages; target two for a non-academic role.',
    accepted: null,
  },
  {
    suggestion_type: 'keywords',
    content:
      'The job families you target expect "CI/CD" and "observability"; both are implied by your work but never stated.',
    accepted: null,
  },
];

/**
 * The career profile served by `GET /profile` in mock mode.
 *
 * Deliberately not a perfect profile: two unevidenced skills and no LinkedIn URL, so
 * the readiness gaps and "no evidence" badges are visible in the demo.
 */
export const MOCK_CAREER_PROFILE: CareerProfileResponse = {
  id: 1,
  headline: 'Senior Frontend Engineer',
  summary:
    'Frontend engineer with eight years building and maintaining large Angular applications. ' +
    'Led a migration off AngularJS across 40 screens and owns the design system used by 12 teams.',
  location: 'Lisbon, Portugal',
  phone: null,
  website_url: null,
  linkedin_url: null,
  experiences: [
    {
      id: 1,
      organisation: 'Tech Corp',
      title: 'Senior Frontend Engineer',
      employment_type: 'full_time',
      location: 'Lisbon, Portugal (hybrid)',
      start_date: '2022-03-01',
      end_date: null,
      description:
        'Led the AngularJS to Angular migration across 40 screens, cutting the bundle by 40%. ' +
        'Owns the component library consumed by 12 teams and 2M monthly users.',
      is_current: true,
    },
    {
      id: 2,
      organisation: 'Northwind Digital',
      title: 'Frontend Engineer',
      employment_type: 'full_time',
      location: 'Porto, Portugal',
      start_date: '2019-06-01',
      end_date: '2022-02-28',
      description:
        'Built the customer portal from scratch in Angular and TypeScript. Took Largest ' +
        'Contentful Paint from 4.2s to 1.1s on the checkout path.',
      is_current: false,
    },
    {
      id: 3,
      organisation: 'Bright Labs',
      title: 'Junior Web Developer',
      employment_type: 'full_time',
      location: 'Braga, Portugal',
      start_date: '2017-09-01',
      end_date: '2019-05-31',
      description: 'Maintained a PHP and jQuery storefront; introduced the first automated tests.',
      is_current: false,
    },
  ],
  educations: [
    {
      id: 1,
      institution: 'University of Minho',
      qualification: 'BSc',
      field_of_study: 'Computer Science',
      start_date: '2014-09-01',
      end_date: '2017-07-31',
      grade: '16/20',
    },
  ],
  skills: [
    {
      id: 1,
      name: 'TypeScript',
      canonical_name: 'typescript',
      category: 'Languages',
      proficiency: 'expert',
      years: 8,
      is_evidenced: true,
      evidence_experience_ids: [1, 2],
    },
    {
      id: 2,
      name: 'Angular',
      canonical_name: 'angular',
      category: 'Frameworks',
      proficiency: 'expert',
      years: 7,
      is_evidenced: true,
      evidence_experience_ids: [1, 2],
    },
    {
      id: 3,
      name: 'RxJS',
      canonical_name: 'rxjs',
      category: 'Frameworks',
      proficiency: 'advanced',
      years: 6,
      is_evidenced: true,
      evidence_experience_ids: [1],
    },
    {
      id: 4,
      name: 'Node.js',
      canonical_name: 'node.js',
      category: 'Backend',
      proficiency: 'intermediate',
      years: 4,
      is_evidenced: true,
      evidence_experience_ids: [2],
    },
    {
      id: 5,
      name: 'PostgreSQL',
      canonical_name: 'postgresql',
      category: 'Backend',
      proficiency: 'intermediate',
      years: 3,
      is_evidenced: false,
      evidence_experience_ids: [],
    },
    {
      id: 6,
      name: 'K8s',
      canonical_name: 'kubernetes',
      category: 'Infrastructure',
      proficiency: 'beginner',
      years: 1,
      is_evidenced: false,
      evidence_experience_ids: [],
    },
  ],
};

/**
 * The deterministic analysis, as `POST /analysis/cvs/{id}/ats-check` returns it.
 *
 * Taken from a real run rather than invented: a two-column layout that survives
 * extraction but reads as fragmented, and a missing phone number. A demo that only
 * shows perfect scores teaches nothing.
 */
export const MOCK_PARSEABILITY: ParseabilityResponse = {
  score: 87,
  word_count: 664,
  findings: [
    {
      code: 'fragmented_layout',
      severity: 'warning',
      message:
        '76% of lines are very short, which is what a multi-column or table layout looks like ' +
        'after extraction. Single-column layouts survive parsing far more reliably.',
    },
    {
      code: 'no_phone',
      severity: 'info',
      message: 'No phone number found. Optional, but many recruiters expect one.',
    },
  ],
  blocking: [],
};

/** `POST /analysis/cvs/{id}/coverage`, against a full-stack posting. */
export const MOCK_COVERAGE: CoverageResponse = {
  score: 43,
  matched: [
    { term: 'typescript', required: true, occurrences: 2 },
    { term: 'react', required: true, occurrences: 1 },
    { term: 'node.js', required: true, occurrences: 1 },
    { term: 'postgresql', required: true, occurrences: 1 },
    { term: 'amazon web services', required: false, occurrences: 1 },
  ],
  missing: [
    { term: 'docker', required: true, occurrences: 1 },
    { term: 'ci/cd', required: true, occurrences: 1 },
    { term: 'rest api', required: true, occurrences: 1 },
    { term: 'full stack', required: true, occurrences: 2 },
    { term: 'kubernetes', required: false, occurrences: 1 },
    { term: 'terraform', required: false, occurrences: 1 },
    { term: 'graphql', required: false, occurrences: 1 },
  ],
  missing_required: [
    { term: 'docker', required: true, occurrences: 1 },
    { term: 'ci/cd', required: true, occurrences: 1 },
    { term: 'rest api', required: true, occurrences: 1 },
    { term: 'full stack', required: true, occurrences: 2 },
  ],
};

/**
 * `POST /profile/import-from-cv/{id}` — a proposal, never stored.
 *
 * A real extraction, imperfections included: one role has a truncated title and one
 * has no dates. Reviewing imperfect rows *is* the feature.
 */
export const MOCK_EXTRACTION: CvExtractionResponse = {
  contact: {
    email: 'dev@cvpal.test',
    phone: '+351 912 345 678',
    linkedin_url: 'linkedin.com/in/devuser',
    website_url: 'github.com/devuser',
  },
  headline: 'Senior Backend Engineer',
  summary:
    'Backend engineer with nine years on payment systems. Comfortable owning a service from schema to on-call rota.',
  location: 'Lisbon, Portugal',
  experiences: [
    {
      organisation: 'Northwind Digital',
      title: 'Senior Software',
      location: 'Lisbon',
      start_date: '2021-06-01',
      end_date: null,
      description: 'Built the payments service in Python and PostgreSQL.',
    },
    {
      organisation: 'Acme Systems',
      title: 'Backend Engineer',
      location: 'Porto',
      start_date: '2018-08-01',
      end_date: '2021-02-01',
      description: 'Maintained a Django monolith.',
    },
    {
      organisation: 'Bright Labs',
      title: 'Junior Developer',
      location: null,
      start_date: null,
      end_date: null,
      description: null,
    },
  ],
  educations: [
    {
      organisation: 'University of Minho',
      title: 'BSc Computer Science',
      location: 'Braga',
      start_date: '2014-09-01',
      end_date: '2017-07-01',
      description: null,
    },
  ],
  skills: ['python', 'postgresql', 'docker', 'kubernetes'],
};

/** `GET /profile/goals`. A remote-preferring backend engineer, with the floor set. */
export const MOCK_GOALS: CareerGoalsResponse = {
  id: 1,
  target_roles: ['Backend Engineer', 'Platform Engineer'],
  work_regimes: ['remote', 'hybrid'],
  regime_non_negotiable: false,
  work_locations: ['Portugal', 'Europe', 'EU'],
  location_non_negotiable: false,
  min_salary: 65000,
  salary_currency: 'EUR',
  salary_non_negotiable: false,
};

/**
 * `GET /jobs` — postings with their scores.
 *
 * One is blocked by a non-negotiable rather than merely ranked low, because that
 * distinction is the point of the goals screen and a demo that never shows it hides the
 * feature. One states its contract and two do not, for the same reason: "not stated" is
 * the common case and the interface has to look right when it happens.
 */
export const MOCK_SCORED_JOBS: readonly ScoredPostingResponse[] = [
  {
    posting: {
      id: 1,
      source: 'greenhouse',
      source_url: 'https://boards.greenhouse.io/acme/jobs/4012345',
      title: 'Senior Backend Engineer',
      company: 'Acme',
      location: 'Remote (EU)',
      description:
        'Requirements: strong Python, PostgreSQL and Docker. Fully remote. ' +
        'Nice to have: Kubernetes, Terraform.',
      employment_type: null,
      created_at: '2026-07-26T09:00:00Z',
    },
    match: {
      score: 78,
      blocked_by: null,
      reasons: [
        { label: 'Skills 74/100', detail: 'Your profile evidences 6 of 9 terms it uses.' },
        { label: 'Title 100/100', detail: '"Senior Backend Engineer" against the roles you are targeting.' },
        { label: 'Work arrangement', detail: 'Offers remote, which you said suits you.' },
      ],
      missing_required: ['kubernetes'],
    },
  },
  {
    posting: {
      id: 2,
      source: 'manual',
      source_url: null,
      title: 'Platform Engineer',
      company: 'Northwind',
      location: 'Munich',
      description: 'On-site in Munich five days a week. Requirements: Go, Kubernetes.',
      employment_type: null,
      created_at: '2026-07-25T16:20:00Z',
    },
    match: {
      score: 0,
      blocked_by: 'You ruled this out: the posting is on site.',
      reasons: [],
      missing_required: [],
    },
  },
  {
    posting: {
      id: 3,
      source: 'remotive',
      source_url:
        'https://remotive.com/remote-jobs/software-development/senior-full-stack-2091100',
      title: 'Senior Full Stack Engineer',
      company: 'Cardinal Labs',
      location: 'Remote · Europe',
      description:
        'Requirements: TypeScript, Angular and Python. Fully remote across Europe. ' +
        'Nice to have: PostgreSQL, Docker.',
      employment_type: 'contract',
      created_at: '2026-07-27T08:10:00Z',
    },
    match: {
      score: 71,
      blocked_by: null,
      reasons: [
        { label: 'Skills 68/100', detail: 'Your profile evidences 5 of 8 terms it uses.' },
        { label: 'Title 95/100', detail: '"Senior Full Stack Engineer" against the roles you are targeting.' },
        { label: 'Work arrangement', detail: 'Offers remote, which you said suits you.' },
      ],
      missing_required: ['graphql'],
    },
  },
];

/**
 * A LinkedIn profile as imported from LinkedIn's own "Save to PDF".
 *
 * Deliberately thin, because the real thing is: that export carries only the top three
 * skills, no About section and no role descriptions. Mock mode showing a rich profile
 * would hide the single most important thing this screen has to tell a user.
 */
export const MOCK_LINKEDIN_PROFILE: LinkedInProfileResponse = {
  source: 'pdf',
  profile_url: 'https://www.linkedin.com/in/dev-cvpal',
  full_name: 'Dev User',
  headline: 'Senior Software Developer at Example Bank',
  about: null,
  positions: [
    {
      organisation: 'Example Bank',
      title: 'Senior Software Developer',
      location: null,
      start_date: '2025-06-01',
      end_date: null,
      description: null,
    },
    {
      organisation: 'Example Bank',
      title: 'Data Analyst',
      location: 'Lisbon, Portugal',
      start_date: '2023-04-01',
      end_date: '2025-08-01',
      description: null,
    },
  ],
  educations: [
    {
      organisation: 'Example Business School',
      title: "Master's degree, Finance",
      location: null,
      start_date: '2016-01-01',
      end_date: '2018-12-01',
      description: null,
    },
  ],
  skills: ['Amazon S3', 'Version Control', 'Jira'],
  sections_found: ['contact', 'top_skills', 'experience', 'education'],
  field_sources: {
    identity: 'pdf',
    positions: 'pdf',
    educations: 'pdf',
    skills: 'pdf',
  },
  imported_at: '2026-07-27T12:00:00Z',
};

export const MOCK_LINKEDIN_REVIEW: LinkedInReviewResponse = {
  score: 70,
  source: 'pdf',
  note: 'Anything you left collapsed when exporting is absent from the document, and reads here as missing.',
  sections: [
    {
      section: 'about',
      status: 'missing',
      detail:
        "No About section found. If you have one, it may have been collapsed when the PDF was made — expand every 'see more' and import again.",
    },
    {
      section: 'skills',
      status: 'thin',
      detail:
        'Only 3 skill(s). Recruiter search filters on these, and a short list drops you out of results you would otherwise be in.',
    },
    { section: 'headline', status: 'ok', detail: 'Senior Software Developer at Example Bank' },
    { section: 'experience', status: 'ok', detail: '2 roles.' },
    { section: 'education', status: 'ok', detail: '1 entries.' },
  ],
  consistency: [
    {
      kind: 'employer_only_on_linkedin',
      organisation: 'Example Bank',
      detail:
        'Example Bank is on LinkedIn but not on your career profile, so nothing CV Pal generates can mention it.',
    },
  ],
  coverage: null,
};
