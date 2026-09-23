import { HttpClient, httpResource } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { CareerGoalsResponse, CareerGoalsUpdate } from '../../shared/models/api.model';
import { AuthService } from './auth.service';

const EMPTY_GOALS: CareerGoalsResponse = {
  id: 0,
  target_roles: [],
  work_regimes: [],
  regime_non_negotiable: false,
  work_locations: [],
  location_non_negotiable: false,
  salary_expectations: [],
  salary_non_negotiable: false,
};

/**
 * What the user is looking for.
 *
 * Read by job matching, so an empty record is not a neutral state — it is why every
 * posting scores the same. The screen says so rather than leaving the user to infer it.
 */
@Injectable({ providedIn: 'root' })
export class GoalsService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);

  private readonly resource = httpResource<CareerGoalsResponse>(
    () => (this.auth.isAuthenticated() ? `${environment.apiUrl}/profile/goals` : undefined),
    { defaultValue: EMPTY_GOALS },
  );

  readonly goals = this.resource.value;
  readonly isLoading = this.resource.isLoading;
  readonly error = this.resource.error;

  reload(): void {
    this.resource.reload();
  }

  /** A replace, not a merge: an omitted preference means the user cleared it. */
  save(payload: CareerGoalsUpdate): Observable<CareerGoalsResponse> {
    return this.http.put<CareerGoalsResponse>(`${environment.apiUrl}/profile/goals`, payload);
  }
}
