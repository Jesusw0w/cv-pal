import { HttpClient, httpResource } from '@angular/common/http';
import { Injectable, computed, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
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
} from '../../shared/models/api.model';
import { AuthService } from './auth.service';

/**
 * What the page shows before `GET /profile` has answered.
 *
 * A real empty profile rather than a placeholder: every gap is reported as missing,
 * which is the truth until the response lands, and it keeps `profile()` non-nullable so
 * the derived signals and the template need no undefined handling.
 */
const EMPTY_PROFILE: CareerProfileResponse = {
  id: 0,
  headline: null,
  summary: null,
  location: null,
  phone: null,
  website_url: null,
  linkedin_url: null,
  experiences: [],
  educations: [],
  skills: [],
};

/** Below this, keyword coverage against a posting is too thin to be worth scoring. */
const MIN_USEFUL_SKILLS = 8;

/**
 * Conditions `gaps` tests unconditionally. Must move with it — it is the completeness
 * denominator.
 *
 * The evidence check is deliberately not counted here: it cannot fail on a profile with
 * no skills, so counting it would award a brand-new account a free pass and score an
 * entirely empty profile 17% instead of 0%. See `applicableChecks`.
 */
const PROFILE_CHECKS = 5;

/** Something the profile is missing, phrased as a task rather than a count. */
export interface ProfileGap {
  label: string;
  /** Why it costs the user something — shown, not implied. */
  detail: string;
}

/**
 * The career profile — the first step of the journey and the record every tailored CV
 * is rendered from.
 */
@Injectable({ providedIn: 'root' })
export class CareerProfileService {
  private readonly auth = inject(AuthService);
  private readonly http = inject(HttpClient);

  /**
   * `GET /profile`, refetched when the session changes.
   *
   * The URL is `undefined` while signed out, which leaves the resource idle rather than
   * firing a request that can only 401 — and reading `isAuthenticated()` here is what
   * makes it load itself the moment a login succeeds.
   */
  private readonly resource = httpResource<CareerProfileResponse>(
    () => (this.auth.isAuthenticated() ? `${environment.apiUrl}/profile` : undefined),
    { defaultValue: EMPTY_PROFILE },
  );

  readonly profile = this.resource.value;
  readonly isLoading = this.resource.isLoading;
  readonly error = this.resource.error;

  reload(): void {
    this.resource.reload();
  }

  /** Newest first: a reader and an ATS both look at the current role before the first one. */
  readonly experiences = computed(() =>
    [...this.profile().experiences].sort((a, b) => b.start_date.localeCompare(a.start_date)),
  );

  readonly educations = computed(() =>
    [...this.profile().educations].sort((a, b) =>
      (b.end_date ?? '').localeCompare(a.end_date ?? ''),
    ),
  );

  /**
   * Skills grouped by category, evidenced first.
   *
   * Ordering by evidence rather than name puts the claims a generated CV may actually
   * use at the top, and leaves the unusable ones visible underneath.
   */
  readonly skillsByCategory = computed<{ category: string; skills: SkillResponse[] }[]>(() => {
    const groups = new Map<string, SkillResponse[]>();
    for (const skill of this.profile().skills) {
      const category = skill.category ?? 'Other';
      groups.set(category, [...(groups.get(category) ?? []), skill]);
    }
    return [...groups.entries()].map(([category, skills]) => ({
      category,
      skills: [...skills].sort((a, b) => Number(b.is_evidenced) - Number(a.is_evidenced)),
    }));
  });

  /**
   * Skills with no dated role behind them.
   *
   * These are the ones a tailored CV must refuse to claim, so surfacing them is not a
   * tidiness feature — it is the difference between a grounded CV and one the user has
   * to defend in an interview.
   */
  readonly ungroundedSkills = computed(() =>
    this.profile().skills.filter((skill) => !skill.is_evidenced),
  );

  /** What the profile still needs before it can drive a tailored CV. */
  readonly gaps = computed<ProfileGap[]>(() => {
    const profile = this.profile();
    const gaps: ProfileGap[] = [];

    if (!profile.headline) {
      gaps.push({
        label: 'Add a headline',
        detail: 'It is the first line recruiters read and the first thing matched against a role.',
      });
    }
    if (!profile.summary) {
      gaps.push({
        label: 'Write a summary',
        detail: 'Tailoring rewrites this per posting, so an empty one wastes the top of the page.',
      });
    }
    if (profile.experiences.length === 0) {
      gaps.push({
        label: 'Add your roles',
        detail: 'Nothing can be tailored or evidenced without dated experience to ground it in.',
      });
    }
    if (profile.skills.length < MIN_USEFUL_SKILLS) {
      gaps.push({
        label: `Add at least ${MIN_USEFUL_SKILLS} skills`,
        detail: 'Keyword coverage against a posting is unreliable below that.',
      });
    }
    if (this.ungroundedSkills().length > 0) {
      gaps.push({
        label: `Evidence ${this.ungroundedSkills().length} skill(s)`,
        detail: 'A skill with no role behind it cannot be written into a generated CV.',
      });
    }
    if (!profile.linkedin_url) {
      gaps.push({
        label: 'Link your LinkedIn profile',
        detail: 'Needed to check the two agree on dates, titles and employers.',
      });
    }

    return gaps;
  });

  /**
   * How many checks the profile is actually being scored against.
   *
   * "Evidence your skills" only applies once there are skills to evidence, so it joins
   * the denominator at the same moment it becomes able to fail. Without this a profile
   * with nothing in it passes a check it was never asked.
   */
  private readonly applicableChecks = computed(
    () => PROFILE_CHECKS + (this.profile().skills.length > 0 ? 1 : 0),
  );

  /**
   * How ready the profile is to generate a tailored CV from.
   *
   * ponytail: flat weights, derived from `gaps` so the number and the list cannot
   * disagree. Weight by CV impact if the score starts misleading.
   */
  readonly completeness = computed(() => {
    const checks = this.applicableChecks();
    return Math.round(((checks - this.gaps().length) / checks) * 100);
  });

  // --- Writes. Every one reloads the profile, so the derived gaps and readiness score
  // move with the data rather than needing their own invalidation. ---

  updateProfile(payload: CareerProfileUpdate): Observable<CareerProfileResponse> {
    return this.http.patch<CareerProfileResponse>(`${environment.apiUrl}/profile`, payload);
  }

  addExperience(payload: ExperienceCreate): Observable<ExperienceResponse> {
    return this.http.post<ExperienceResponse>(`${environment.apiUrl}/profile/experiences`, payload);
  }

  updateExperience(id: number, payload: ExperienceUpdate): Observable<ExperienceResponse> {
    return this.http.patch<ExperienceResponse>(
      `${environment.apiUrl}/profile/experiences/${id}`,
      payload,
    );
  }

  deleteExperience(id: number): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/profile/experiences/${id}`);
  }

  addEducation(payload: EducationCreate): Observable<EducationResponse> {
    return this.http.post<EducationResponse>(`${environment.apiUrl}/profile/educations`, payload);
  }

  updateEducation(id: number, payload: EducationUpdate): Observable<EducationResponse> {
    return this.http.patch<EducationResponse>(
      `${environment.apiUrl}/profile/educations/${id}`,
      payload,
    );
  }

  deleteEducation(id: number): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/profile/educations/${id}`);
  }

  addSkill(payload: SkillCreate): Observable<SkillResponse> {
    return this.http.post<SkillResponse>(`${environment.apiUrl}/profile/skills`, payload);
  }

  /** Amend a skill. `evidence_experience_ids` replaces the citations when sent. */
  updateSkill(id: number, payload: SkillUpdate): Observable<SkillResponse> {
    return this.http.patch<SkillResponse>(`${environment.apiUrl}/profile/skills/${id}`, payload);
  }

  deleteSkill(id: number): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/profile/skills/${id}`);
  }

  /**
   * Read structured records out of an uploaded CV.
   *
   * Proposes only — the endpoint stores nothing, and the caller creates whatever the
   * user keeps through the add methods above.
   */
  importFromCv(cvId: number): Observable<CvExtractionResponse> {
    return this.http.post<CvExtractionResponse>(
      `${environment.apiUrl}/profile/import-from-cv/${cvId}`,
      null,
    );
  }

  /**
   * Ask which roles already name each skill.
   *
   * Proposes only. The citations reach the profile through `updateSkill`, which is what
   * keeps a guess from becoming a claim on a CV without the user seeing it.
   */
  evidenceSuggestions(): Observable<EvidenceSuggestionResponse[]> {
    return this.http.get<EvidenceSuggestionResponse[]>(
      `${environment.apiUrl}/profile/skills/evidence-suggestions`,
    );
  }

  /**
   * Draft a summary from the facts already in the profile.
   *
   * Proposes only, like `importFromCv`: the draft is shown, and it reaches the profile
   * through `updateProfile` if the user keeps it. The only profile call that needs a
   * model configured — it fails with 502 when there is none.
   */
  generateSummary(): Observable<ProfileSummaryResponse> {
    return this.http.post<ProfileSummaryResponse>(`${environment.apiUrl}/profile/summary`, null);
  }

  /**
   * Whether the account has nothing in it yet.
   *
   * Drives the first-run redirect. Deliberately not "is the profile complete": someone
   * who has entered one role and stopped has made a choice, and being sent back to a
   * wizard would override it.
   */
  readonly isEmpty = computed(() => {
    const profile = this.profile();
    return (
      profile.experiences.length === 0 &&
      profile.educations.length === 0 &&
      profile.skills.length === 0 &&
      !profile.headline &&
      !profile.summary
    );
  });
}
