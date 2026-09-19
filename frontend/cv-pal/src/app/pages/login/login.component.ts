import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { AuthService } from '../../core/services/auth.service';

/**
 * What brought the user back to this screen, when it was not simply signing out.
 *
 * A password change revokes every session, so it lands here — and without a word of
 * explanation an intentional change looks exactly like being kicked out.
 */
const NOTICES: Record<string, string> = {
  'password-changed':
    'Password changed. Every device was signed out, including this one — sign in with the new password.',
};

@Component({
  selector: 'app-login',
  imports: [FormsModule],
  template: `
    <main class="shell">
      <form class="card panel" (ngSubmit)="submit()">
        <img src="logo.webp" alt="" class="mark" />
        <h1>{{ registering() ? 'Create an account' : 'Sign in' }}</h1>

        @if (registering()) {
          <label>
            Name
            <input name="fullName" [(ngModel)]="fullName" autocomplete="name" />
          </label>
        }

        <label>
          Email
          <input name="email" type="email" [(ngModel)]="email" autocomplete="username" required />
        </label>

        <label>
          Password
          <input
            name="password"
            type="password"
            [(ngModel)]="password"
            [attr.autocomplete]="registering() ? 'new-password' : 'current-password'"
            required
          />
          @if (registering()) {
            <small>At least 12 characters. Long beats complicated.</small>
          }
        </label>

        @if (notice(); as message) {
          <p class="notice" role="status">{{ message }}</p>
        }

        @if (error(); as message) {
          <p class="error" role="alert">{{ message }}</p>
        }

        <button type="submit" class="primary" [disabled]="busy()">
          {{ busy() ? 'Working…' : registering() ? 'Create account' : 'Sign in' }}
        </button>

        <button type="button" class="link" (click)="toggleMode()">
          {{ registering() ? 'I already have an account' : 'Create an account' }}
        </button>
      </form>
    </main>
  `,
  styles: [
    `
      .shell {
        min-height: 100dvh;
        display: grid;
        place-items: center;
        padding: 24px;
      }
      .panel {
        display: flex;
        flex-direction: column;
        gap: 14px;
        padding: 28px;
        width: min(380px, 100%);
      }
      .mark {
        width: 48px;
        height: 48px;
        align-self: center;
      }
      h1 {
        font-size: 18px;
        margin: 0;
        text-align: center;
      }
      label {
        display: flex;
        flex-direction: column;
        gap: 6px;
        font-size: 13px;
        color: var(--text-secondary);
      }
      input {
        padding: 10px 12px;
        border: 1px solid var(--border-light);
        border-radius: var(--radius);
        background: var(--bg-primary);
        color: var(--text-primary);
        font-size: 14px;
      }
      small {
        font-size: 11px;
        color: var(--text-tertiary);
      }
      .error {
        margin: 0;
        font-size: 13px;
        color: var(--danger, #dc2626);
      }
      .notice {
        margin: 0;
        font-size: 13px;
        line-height: 1.5;
        color: var(--text-secondary);
        border-left: 2px solid var(--accent);
        padding-left: 10px;
      }
      .primary {
        padding: 10px;
        border-radius: var(--radius);
        background: var(--accent);
        color: #fff;
        font-size: 14px;
        font-weight: 600;
      }
      .primary:disabled {
        opacity: 0.6;
      }
      .link {
        font-size: 13px;
        color: var(--text-tertiary);
      }
      .link:hover {
        color: var(--text-primary);
      }
    `,
  ],
})
export class LoginComponent {
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  readonly registering = signal(false);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);

  /** Set from `?reason=`, so the redirect carries its own explanation. */
  readonly notice = signal<string | null>(
    NOTICES[this.route.snapshot.queryParamMap.get('reason') ?? ''] ?? null,
  );

  email = '';
  password = '';
  fullName = '';

  toggleMode(): void {
    this.registering.update((value) => !value);
    this.error.set(null);
  }

  submit(): void {
    this.busy.set(true);
    this.error.set(null);

    // Registering does not sign you in, so it chains into a login with the same
    // credentials rather than leaving the user on a form that just succeeded.
    const request = this.registering()
      ? this.auth.register(this.email, this.password, this.fullName || null)
      : null;

    if (request === null) {
      this.signIn();
      return;
    }

    request.subscribe({
      next: () => this.signIn(),
      error: (error: unknown) => this.fail(error),
    });
  }

  private signIn(): void {
    this.auth.login(this.email, this.password).subscribe({
      next: () => {
        this.busy.set(false);
        void this.router.navigate(['/dashboard']);
      },
      error: (error: unknown) => this.fail(error),
    });
  }

  private fail(error: unknown): void {
    this.busy.set(false);
    this.error.set(detailOf(error) ?? 'Something went wrong. Is the API running?');
  }
}

/**
 * The message to show for a failed request.
 *
 * The API answers in two shapes: a flat `detail` string for domain errors like bad
 * credentials, and FastAPI's list of validation objects for a 422 — which is what every
 * password-policy rejection arrives as. Reading `detail` blindly would show the user a
 * stringified array instead of the rule they broke, on the one screen where the reason
 * is the whole point.
 */
export function detailOf(error: unknown): string | null {
  if (!(error instanceof HttpErrorResponse)) {
    return null;
  }

  const detail = (error.error as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail)) {
    const message = (detail[0] as { msg?: unknown } | undefined)?.msg;
    // Pydantic prefixes its own validators' messages.
    return typeof message === 'string' ? message.replace(/^Value error, /, '') : null;
  }
  return null;
}
