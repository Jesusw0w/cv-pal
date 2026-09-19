import { HttpClient, httpResource } from '@angular/common/http';
import { Injectable, computed, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  LinkedInProfileResponse,
  LinkedInReviewResponse,
  LinkedInSource,
} from '../../shared/models/api.model';
import { AuthService } from './auth.service';

/** What the API accepts. A ZIP is the official data export; a PDF is either profile print. */
export const ALLOWED_LINKEDIN_EXTENSIONS = ['.pdf', '.zip'] as const;
export const MAX_LINKEDIN_BYTES = 10 * 1024 * 1024;
/** The API refuses a shorter paste than this, so the button stays disabled until then. */
export const MIN_LINKEDIN_PASTE_LENGTH = 120;

/**
 * The imported LinkedIn profile and its review.
 *
 * **Nothing here fetches linkedin.com.** The profile arrives as a document the user
 * exported themselves — see `docs/linkedin-import.md`. The review is deterministic, so
 * like the CV analysis it works on a fresh install with no model configured.
 */
@Injectable({ providedIn: 'root' })
export class LinkedInService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);

  /**
   * `GET /linkedin`, idle while signed out.
   *
   * 404 is the ordinary state before a first import rather than an error worth showing,
   * so `hasProfile` reads the value instead of the status.
   */
  private readonly snapshot = httpResource<LinkedInProfileResponse>(() =>
    this.auth.isAuthenticated() ? `${environment.apiUrl}/linkedin` : undefined,
  );

  private readonly reviewResource = httpResource<LinkedInReviewResponse>(() =>
    this.auth.isAuthenticated() ? `${environment.apiUrl}/linkedin/review` : undefined,
  );

  readonly profile = this.snapshot.value;
  readonly review = this.reviewResource.value;
  readonly isLoading = computed(() => this.snapshot.isLoading() || this.reviewResource.isLoading());

  readonly hasProfile = computed(() => this.profile() !== undefined);

  /**
   * Whether the official data export would still add anything.
   *
   * The PDF routes carry only the top three skills and no About section, so a user who
   * imported one is told what they are still missing rather than left to wonder why the
   * review is thin.
   */
  readonly wouldBenefitFromExport = computed(() => needsDataExport(this.profile()?.field_sources));

  reload(): void {
    this.snapshot.reload();
    this.reviewResource.reload();
  }

  /** Import a profile PDF or the official data-export archive. */
  upload(file: File): Observable<LinkedInProfileResponse> {
    const body = new FormData();
    body.append('file', file);
    return this.http.post<LinkedInProfileResponse>(`${environment.apiUrl}/linkedin/import`, body);
  }

  /** Import a profile the user copied out of the page. */
  paste(text: string): Observable<LinkedInProfileResponse> {
    const body = new FormData();
    body.append('text', text);
    return this.http.post<LinkedInProfileResponse>(`${environment.apiUrl}/linkedin/import`, body);
  }

  delete(): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/linkedin`);
  }
}

/**
 * A pure function over the provenance map rather than a method on the service, so the
 * rule can be tested without standing up a resource. Undefined means nothing has been
 * imported yet, which is not a gap worth reporting.
 */
export function needsDataExport(fieldSources: Record<string, LinkedInSource> | undefined): boolean {
  if (fieldSources === undefined) {
    return false;
  }
  return Object.values(fieldSources).some((source) => source !== 'export');
}

/**
 * Why an import cannot be accepted, or null when it can.
 *
 * Checked client-side purely for an instant answer — the API enforces the same rules.
 */
export function rejectLinkedInFile(file: File): string | null {
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
  if (
    !ALLOWED_LINKEDIN_EXTENSIONS.includes(extension as (typeof ALLOWED_LINKEDIN_EXTENSIONS)[number])
  ) {
    return 'Upload the profile PDF, or the ZIP from a LinkedIn data export.';
  }
  if (file.size > MAX_LINKEDIN_BYTES) {
    return 'That file is over the 10 MB limit.';
  }
  return null;
}
