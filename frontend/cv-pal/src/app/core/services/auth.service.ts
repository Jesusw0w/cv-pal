import { HttpClient, httpResource } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, finalize, shareReplay, tap } from 'rxjs';

import { environment } from '../../../environments/environment';
import { TokenResponse, UserResponse } from '../../shared/models/api.model';

/** Whether this browser holds a session. Not a secret: the tokens are HttpOnly cookies. */
const SIGNED_IN_KEY = 'cv-pal.signed-in';
/** Where tokens used to be kept, before they moved into cookies. Cleared on load. */
const LEGACY_KEYS = ['cv-pal.access-token', 'cv-pal.refresh-token'];

/**
 * `localStorage`, or nothing where there is no browser — the test runner and any
 * server-side render. Resolved once here so every read and write routes through one
 * guard instead of each call site growing its own.
 */
const store: Storage | null = typeof localStorage === 'undefined' ? null : localStorage;
LEGACY_KEYS.forEach((key) => store?.removeItem(key));

/**
 * The session, as far as the page can know it.
 *
 * Both tokens are HttpOnly cookies set by the API, so script on the page — including
 * injected script — never sees them. What the page keeps is only whether it is signed
 * in, so the guard can route without a request.
 *
 * In a mock build the session starts already established, so the public demo needs no
 * account and the guard and interceptor still run their real code paths.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);

  private readonly signedIn = signal(
    environment.useMocks || store?.getItem(SIGNED_IN_KEY) === 'true',
  );

  /**
   * The refresh in progress, shared between subscribers.
   *
   * Load-bearing: refresh tokens are single-use and the backend revokes *every* session
   * when one is presented twice. Two requests 401-ing at once would therefore log the
   * user out of everything unless they share one refresh call.
   */
  private inFlight: Observable<TokenResponse> | null = null;

  readonly isAuthenticated = this.signedIn.asReadonly();

  /** The signed-in account. Idle while signed out, so it never fires a doomed request. */
  private readonly account = httpResource<UserResponse>(() =>
    this.isAuthenticated() ? `${environment.apiUrl}/users/me` : undefined,
  );

  /**
   * What to call the user in the interface.
   *
   * Falls back to the email when no name was given at registration — `full_name` is
   * optional on the API, and a blank sidebar is worse than an email address.
   */
  readonly displayName = computed(
    () => this.account.value()?.full_name || this.account.value()?.email || '',
  );

  /** The stored name, unfallen-back: what an edit field has to start from. */
  readonly fullName = computed(() => this.account.value()?.full_name ?? null);

  /** Identifies the account for anything kept per user in this browser. */
  readonly userId = computed(() => this.account.value()?.id ?? null);

  readonly initials = computed(() => {
    const name = this.displayName();
    const parts = name.split(/[\s@.]+/).filter(Boolean);
    return parts
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  });

  login(email: string, password: string): Observable<TokenResponse> {
    // OAuth2 password flow: form-encoded, with the email carried in `username`.
    const body = new URLSearchParams({ username: email, password });
    return this.http
      .post<TokenResponse>(`${environment.apiUrl}/auth/login`, body.toString(), {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      .pipe(tap(() => this.markSignedIn(true)));
  }

  register(email: string, password: string, fullName: string | null): Observable<UserResponse> {
    return this.http.post<UserResponse>(`${environment.apiUrl}/auth/register`, {
      email,
      password,
      full_name: fullName,
    });
  }

  refresh(): Observable<TokenResponse> {
    this.inFlight ??= this.http
      .post<TokenResponse>(`${environment.apiUrl}/auth/refresh`, null)
      .pipe(
        finalize(() => (this.inFlight = null)),
        shareReplay({ bufferSize: 1, refCount: false }),
      );

    return this.inFlight;
  }

  /** End this session. The local half is dropped first — server revocation is best effort. */
  logout(): void {
    this.clearSession();
    this.http.post(`${environment.apiUrl}/auth/logout`, null).subscribe({ error: () => undefined });
  }

  /**
   * Set the name every generated CV is headed with.
   *
   * Reloads the account so the sidebar and the next generated document agree with what
   * was just typed.
   */
  updateName(fullName: string | null): Observable<UserResponse> {
    return this.http
      .patch<UserResponse>(`${environment.apiUrl}/users/me`, { full_name: fullName })
      .pipe(tap(() => this.account.reload()));
  }

  /**
   * Change the password. The server revokes every session including this one, so the
   * caller signs out locally rather than holding tokens that will 401 on the next move.
   */
  changePassword(currentPassword: string, newPassword: string): Observable<void> {
    return this.http.patch<void>(`${environment.apiUrl}/users/me/password`, {
      current_password: currentPassword,
      new_password: newPassword,
    });
  }

  /** Delete the account and everything in it. Irreversible; the password confirms it. */
  deleteAccount(password: string): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/users/me`, {
      body: { password },
    });
  }

  clearSession(): void {
    this.markSignedIn(false);
  }

  private markSignedIn(value: boolean): void {
    if (value) {
      store?.setItem(SIGNED_IN_KEY, 'true');
    } else {
      store?.removeItem(SIGNED_IN_KEY);
    }
    this.signedIn.set(value);
  }
}
