import { HttpClient, httpResource } from '@angular/common/http';
import { Injectable, computed, inject } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  ApplicationCreate,
  ApplicationResponse,
  ApplicationStatsResponse,
  ApplicationStatus,
  ApplicationUpdate,
  JobPostingResponse,
} from '../../shared/models/api.model';
import { AuthService } from './auth.service';

/** Statuses in the order an application passes through them, for the funnel. */
export const PIPELINE: ApplicationStatus[] = ['applied', 'interviewing', 'offer'];

const EMPTY_STATS: ApplicationStatsResponse = {
  total: 0,
  by_status: { applied: 0, interviewing: 0, offer: 0, rejected: 0, withdrawn: 0 },
  replied: 0,
  answerable: 0,
  reply_rate: null,
  needs_chasing: 0,
};

/**
 * Applications: what went out, and what came back.
 *
 * The stats are fetched rather than derived from the list, because reply rate depends
 * on how old each application is — a rule the server already owns, and one that would
 * drift the moment it was reimplemented here.
 */
@Injectable({ providedIn: 'root' })
export class ApplicationService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);

  private readonly resource = httpResource<ApplicationResponse[]>(
    () => (this.auth.isAuthenticated() ? `${environment.apiUrl}/applications` : undefined),
    { defaultValue: [] },
  );

  private readonly statsResource = httpResource<ApplicationStatsResponse>(
    () => (this.auth.isAuthenticated() ? `${environment.apiUrl}/applications/stats` : undefined),
    { defaultValue: EMPTY_STATS },
  );

  /** Saved postings with no application against them — what there is left to do. */
  private readonly unappliedResource = httpResource<JobPostingResponse[]>(
    () =>
      this.auth.isAuthenticated() ? `${environment.apiUrl}/applications/unapplied` : undefined,
    { defaultValue: [] },
  );

  readonly applications = this.resource.value;
  readonly stats = this.statsResource.value;
  readonly unapplied = this.unappliedResource.value;
  readonly isLoading = this.resource.isLoading;
  readonly error = this.resource.error;

  /** The ones that have gone quiet, oldest first: the follow-ups worth doing today. */
  readonly needsChasing = computed(() =>
    this.applications()
      .filter((application) => application.needs_chasing)
      .sort((a, b) => b.days_since_applied - a.days_since_applied),
  );

  /** Postings already applied for, so the job list can say so without asking per row. */
  readonly appliedPostingIds = computed(
    () => new Set(this.applications().map((application) => application.posting.id)),
  );

  reload(): void {
    this.resource.reload();
    this.statsResource.reload();
    this.unappliedResource.reload();
  }

  record(payload: ApplicationCreate): Observable<ApplicationResponse> {
    return this.http
      .post<ApplicationResponse>(`${environment.apiUrl}/applications`, payload)
      .pipe(tap(() => this.reload()));
  }

  update(id: number, payload: ApplicationUpdate): Observable<ApplicationResponse> {
    return this.http
      .patch<ApplicationResponse>(`${environment.apiUrl}/applications/${id}`, payload)
      .pipe(tap(() => this.reload()));
  }

  remove(id: number): Observable<void> {
    return this.http
      .delete<void>(`${environment.apiUrl}/applications/${id}`)
      .pipe(tap(() => this.reload()));
  }
}
