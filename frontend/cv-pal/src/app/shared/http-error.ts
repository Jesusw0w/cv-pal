import { HttpErrorResponse } from '@angular/common/http';

/** The API's own message for a failed request, or `fallback` when it gave none. */
export function detailOf(error: unknown, fallback: string): string {
  if (error instanceof HttpErrorResponse) {
    const detail = (error.error as { detail?: unknown } | null)?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    // 422 from Pydantic arrives as a list of per-field errors; the password policy
    // messages the user needs are inside them.
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => (item as { msg?: unknown }).msg)
        .filter((msg): msg is string => typeof msg === 'string')
        .map((msg) => msg.replace(/^Value error, /, ''));
      if (messages.length > 0) {
        return messages.join(' ');
      }
    }
  }
  return fallback;
}
