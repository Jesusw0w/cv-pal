import { HttpErrorResponse } from '@angular/common/http';

/**
 * The API's own message for a failed request, or `fallback` when it gave none.
 *
 * The API answers in two shapes: a flat `detail` string for domain errors, and FastAPI's
 * list of validation objects for a 422 — which is how every password-policy and goals
 * rejection arrives. Those messages are guidance the user needs, so they are shown.
 */
export function detailOf(error: unknown, fallback: string): string {
  if (!(error instanceof HttpErrorResponse)) {
    return fallback;
  }
  const detail = (error.error as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item as { msg?: unknown }).msg)
      .filter((msg): msg is string => typeof msg === 'string')
      // Pydantic prefixes its own validators' messages.
      .map((msg) => msg.replace(/^Value error, /, ''));
    if (messages.length > 0) {
      return messages.join(' ');
    }
  }
  return fallback;
}
