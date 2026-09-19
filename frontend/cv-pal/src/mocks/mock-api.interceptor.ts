import {
  HttpErrorResponse,
  HttpEvent,
  HttpHandlerFn,
  HttpHeaders,
  HttpInterceptorFn,
  HttpRequest,
  HttpResponse,
} from '@angular/common/http';
import { Observable, delay, of, throwError } from 'rxjs';

import { environment } from '../environments/environment';
import { MockBackend, MockHttpError } from './mock-backend';

/** Single store instance, so mutations persist across requests within a session. */
const backend = new MockBackend();

/** Reset the mock store. Exposed for tests. */
export function resetMockBackend(): void {
  backend.reset();
}

/**
 * Serve every request from local fixtures instead of the network.
 *
 * Registered only when `environment.useMocks` is true — see `app.config.ts`. It is
 * never a fallback for a failing API: in a non-mock build this interceptor is not in
 * the chain at all, so real errors surface as real errors.
 */
export const mockApiInterceptor: HttpInterceptorFn = (
  request: HttpRequest<unknown>,
  next: HttpHandlerFn,
): Observable<HttpEvent<unknown>> => {
  if (!environment.useMocks) {
    return next(request);
  }

  const latency = environment.mockLatencyMs;

  if (environment.mockErrorRate > 0 && Math.random() < environment.mockErrorRate) {
    return throwError(
      () =>
        new HttpErrorResponse({
          status: 500,
          statusText: 'Injected mock failure',
          url: request.url,
          error: { detail: 'Injected mock failure' },
        }),
    ).pipe(delay(latency));
  }

  let result;
  try {
    result = backend.handle(request);
  } catch (error) {
    if (error instanceof MockHttpError) {
      return throwError(
        () =>
          new HttpErrorResponse({
            status: error.status,
            statusText: error.detail,
            url: request.url,
            error: { detail: error.detail },
          }),
      ).pipe(delay(latency));
    }
    throw error;
  }

  if (result === null) {
    // Loud by design: an unmapped route means a missing fixture, and silently
    // falling through to the network would defeat the point of mock mode.
    const detail = `No mock route for ${request.method} ${request.url}`;
    console.warn(`[mock] ${detail}`);
    return throwError(
      () =>
        new HttpErrorResponse({
          status: 404,
          statusText: 'No mock route',
          url: request.url,
          error: { detail },
        }),
    ).pipe(delay(latency));
  }

  return of(
    new HttpResponse({
      status: result.status,
      body: result.body,
      url: request.url,
      headers: result.headers ? new HttpHeaders(result.headers) : undefined,
    }),
  ).pipe(delay(latency));
};
