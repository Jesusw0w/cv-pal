import { HttpClient, httpResource } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  ApiTokenCreate,
  ApiTokenCreatedResponse,
  ApiTokenListResponse,
} from '../../shared/models/api.model';

/** Personal access tokens: how an agent the user runs reaches CV Pal over MCP. */
@Injectable({ providedIn: 'root' })
export class ApiTokenService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/users/me/tokens`;

  readonly tokens = httpResource<ApiTokenListResponse>(() => this.base);

  /** The MCP endpoint's address, as an agent on this machine should be given it. */
  readonly endpoint = new URL(`${environment.apiUrl}/mcp`, globalThis.location?.href).href;

  create(payload: ApiTokenCreate): Observable<ApiTokenCreatedResponse> {
    return this.http
      .post<ApiTokenCreatedResponse>(this.base, payload)
      .pipe(tap(() => this.tokens.reload()));
  }

  revoke(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`).pipe(tap(() => this.tokens.reload()));
  }
}
