import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';

import { AuthService } from './services/auth.service';

/**
 * The session lives in HttpOnly cookies the page cannot read. Every request sends them
 * along with the header that asks for cookie mode — which is also what the backend
 * checks to tell this app from a forged cross-site request.
 */
export const SESSION_HEADER = 'X-CV-Pal-Session';

/** Send the session, and refresh once when the API says it has expired. */
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const withSession = asSession(request);

  // The auth endpoints are how a session is obtained. Refreshing a failed login, or a
  // refresh that just failed, loops.
  if (request.url.includes('/auth/')) {
    return next(withSession);
  }

  return next(withSession).pipe(
    catchError((error: unknown) => {
      const expired = error instanceof HttpErrorResponse && error.status === 401;
      if (!expired || !auth.isAuthenticated()) {
        return throwError(() => error);
      }

      return auth.refresh().pipe(
        // Only a failed *refresh* ends the session. Placed after the replay, this would
        // also catch the replayed request's own error — so a wrong current password on
        // "change password" (a 401) signed the user out.
        catchError((refreshError: unknown) => {
          // The refresh token is gone or was reused, so every session is now revoked.
          auth.clearSession();
          void router.navigate(['/login']);
          return throwError(() => refreshError);
        }),
        switchMap(() => next(withSession)),
      );
    }),
  );
};

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  return auth.isAuthenticated() || inject(Router).createUrlTree(['/login']);
};

function asSession(request: HttpRequest<unknown>): HttpRequest<unknown> {
  return request.clone({ withCredentials: true, setHeaders: { [SESSION_HEADER]: 'cookie' } });
}
