import { signal } from '@angular/core';
import { Observable } from 'rxjs';

import { detailOf } from './http-error';

/**
 * One write at a time: whether it is running, and why the last one failed.
 *
 * Every screen needs the same three things around a request — disable the button, clear
 * the old error, show the API's message on failure — so they live here once.
 */
export class Action {
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);

  run<T>(request: Observable<T>, fallback: string, onDone?: (value: T) => void): void {
    this.busy.set(true);
    this.error.set(null);
    request.subscribe({
      next: (value) => {
        this.busy.set(false);
        onDone?.(value);
      },
      error: (error: unknown) => {
        this.busy.set(false);
        this.error.set(detailOf(error, fallback));
      },
    });
  }
}
