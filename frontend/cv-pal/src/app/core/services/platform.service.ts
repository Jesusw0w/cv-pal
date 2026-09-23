import { HttpClient, httpResource } from '@angular/common/http';
import { Injectable, computed, inject } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  JobPlatformCreate,
  JobPlatformResponse,
  JobPlatformUpdate,
} from '../../shared/models/api.model';
import { ApplicationService } from './application.service';
import { AuthService } from './auth.service';

/**
 * Job platforms the user keeps a profile on — entirely optional.
 *
 * Each one says whether it still shows an older version of the profile, and the
 * applications screen offers them as where an application was sent through, so reply
 * rates can be compared per platform.
 */
@Injectable({ providedIn: 'root' })
export class PlatformService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly applications = inject(ApplicationService);

  private readonly resource = httpResource<JobPlatformResponse[]>(
    () => (this.auth.isAuthenticated() ? `${environment.apiUrl}/platforms` : undefined),
    { defaultValue: [] },
  );

  readonly platforms = this.resource.value;
  readonly isLoading = this.resource.isLoading;
  readonly error = this.resource.error;

  /** Platforms whose copy of the profile is behind, for a nudge elsewhere in the app. */
  readonly outdated = computed(() =>
    this.platforms().filter((platform) => platform.status === 'outdated'),
  );

  /** Statuses are computed against the profile, so a profile edit makes them stale. */
  reload(): void {
    this.resource.reload();
  }

  add(payload: JobPlatformCreate): Observable<JobPlatformResponse> {
    return this.http
      .post<JobPlatformResponse>(`${environment.apiUrl}/platforms`, payload)
      .pipe(tap(() => this.reload()));
  }

  update(id: number, payload: JobPlatformUpdate): Observable<JobPlatformResponse> {
    return this.http
      .patch<JobPlatformResponse>(`${environment.apiUrl}/platforms/${id}`, payload)
      .pipe(tap(() => this.reload()));
  }

  /** Applications through it are kept, unlinked — so their stats move to "Not recorded". */
  remove(id: number): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/platforms/${id}`).pipe(
      tap(() => {
        this.reload();
        this.applications.reload();
      }),
    );
  }
}
