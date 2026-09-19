import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';

import { AuthService } from './services/auth.service';

/** Attach the bearer token, and refresh once when the API says it has expired. */
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  // The auth endpoints are how a token is obtained. Sending a stale one at them, or
  // trying to refresh a refresh that just failed, loops.
  if (request.url.includes('/auth/')) {
    return next(request);
  }

  return next(withToken(request, auth.accessToken())).pipe(
    catchError((error: unknown) => {
      const expired = error instanceof HttpErrorResponse && error.status === 401;
      if (!expired || !auth.hasRefreshToken()) {
        return throwError(() => error);
      }

      return auth.refresh().pipe(
        switchMap((tokens) => next(withToken(request, tokens.access_token))),
        catchError((refreshError: unknown) => {
          // The refresh token is gone or was reused, so every session is now revoked.
          auth.clearSession();
          void router.navigate(['/login']);
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  return auth.isAuthenticated() || inject(Router).createUrlTree(['/login']);
};

function withToken(request: HttpRequest<unknown>, token: string | null): HttpRequest<unknown> {
  return token === null
    ? request
    : request.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
}
