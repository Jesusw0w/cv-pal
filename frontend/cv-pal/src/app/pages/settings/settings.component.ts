import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { environment } from '../../../environments/environment';
import { AuthService } from '../../core/services/auth.service';
import { ThemeService } from '../../core/services/theme.service';
import { forgetWelcome } from '../../core/first-run';

/**
 * Settings: only the controls that do something.
 *
 * An earlier version had a nav that did not navigate, Billing for a self-hosted MIT
 * project, and toggles no code read. A control that does nothing is worse than an
 * absent one.
 */
@Component({
  selector: 'app-settings',
  template: `
    <div class="page">
      <section class="card">
        <div class="card-header"><h3>Account</h3></div>
        <div class="rows">
          <div class="row">
            <div class="row-info">
              <span class="row-label">Signed in as</span>
              <span class="row-desc">{{ auth.displayName() || 'Loading…' }}</span>
            </div>
            <button type="button" class="danger" (click)="signOut()">Sign out</button>
          </div>
        </div>
        <div class="rows form">
          <label class="field">
            <span>Your name</span>
            <input type="text" autocomplete="name"
              [value]="fullName()" (input)="fullName.set(value($event))" />
          </label>
          <p class="hint">
            The heading of every CV and cover letter CV Pal generates. Leave it empty and
            they are titled "Curriculum Vitae".
          </p>
          @if (nameError(); as message) {
            <p class="error" role="alert">{{ message }}</p>
          }
          @if (nameSaved()) {
            <p class="ok" role="status">Saved.</p>
          }
          <div class="right">
            <button type="button" class="primary" [disabled]="busy()" (click)="saveName()">
              {{ busy() ? 'Saving…' : 'Save name' }}
            </button>
          </div>
        </div>
        <div class="rows">
          <div class="row">
            <div class="row-info">
              <span class="row-label">Guided setup</span>
              <span class="row-desc">
                Walk through the CV import, the profile basics and your goals again.
                Nothing is cleared — the steps start from what you already have.
              </span>
            </div>
            <button type="button" class="ghost-btn" (click)="rerunSetup()">Run again</button>
          </div>
        </div>
      </section>

      <section class="card">
        <div class="card-header"><h3>Appearance</h3></div>
        <div class="rows">
          <div class="row">
            <div class="row-info">
              <span class="row-label">Dark mode</span>
              <span class="row-desc">Switch between light and dark themes</span>
            </div>
            <button
              type="button"
              class="toggle"
              role="switch"
              [attr.aria-checked]="theme.dark()"
              aria-label="Dark mode"
              [class.active]="theme.dark()"
              (click)="theme.toggle()"
            >
              <span class="toggle-knob"></span>
            </button>
          </div>
        </div>
      </section>

      <section class="card">
        <div class="card-header"><h3>Password</h3></div>
        <div class="rows form">
          <label class="field">
            <span>Current password</span>
            <input type="password" autocomplete="current-password"
              [value]="currentPassword()" (input)="currentPassword.set(value($event))" />
          </label>
          <label class="field">
            <span>New password</span>
            <input type="password" autocomplete="new-password"
              [value]="newPassword()" (input)="newPassword.set(value($event))" />
          </label>
          <label class="field">
            <span>Confirm new password</span>
            <input type="password" autocomplete="new-password"
              [value]="confirmPassword()" (input)="confirmPassword.set(value($event))" />
          </label>
          @if (mismatch()) {
            <p class="error" role="alert">Those two do not match.</p>
          }
          <p class="hint">
            At least 12 characters. Length beats punctuation — a phrase you can remember
            is stronger than a short password with symbols in it.
          </p>
          @if (passwordError(); as message) {
            <p class="error" role="alert">{{ message }}</p>
          }
          <div class="right">
            <button type="button" class="primary"
              [disabled]="!canChangePassword() || busy()"
              (click)="changePassword()">
              {{ busy() ? 'Changing…' : 'Change password' }}
            </button>
          </div>
          <p class="hint">
            Changing it signs out every device, this one included. Locked out with no
            way in? There is no reset email — a self-hosted instance usually has no mail
            server, and a reset link that cannot be delivered would be worse than none.
            Recover from a terminal on the machine running CV Pal:
            <code>docker compose exec backend python -m cv_pal.admin reset-password
            your@email</code>
          </p>
        </div>
      </section>

      <section class="card">
        <div class="card-header"><h3>Your data</h3></div>
        <div class="rows">
          <div class="row">
            <div class="row-info">
              <span class="row-label">Download everything</span>
              <span class="row-desc">
                Your profile, goals, saved postings and the list of your documents, as
                one JSON file. Uploaded files are downloaded from Documents.
              </span>
            </div>
            <button type="button" class="ghost-btn" [disabled]="exporting()" (click)="exportData()">
              {{ exporting() ? 'Preparing…' : 'Download' }}
            </button>
          </div>
          @if (exportError(); as message) {
            <p class="error" role="alert">{{ message }}</p>
          }
        </div>
      </section>

      <section class="card danger-card">
        <div class="card-header"><h3>Delete this account</h3></div>
        <div class="rows form">
          <p class="hint">
            Removes your profile, goals, uploaded CVs and their files, saved postings and
            letters. It happens immediately and cannot be undone — there is no soft
            delete and no copy kept. Download your data first if you want a copy.
          </p>
          @if (!confirming()) {
            <div class="right">
              <button type="button" class="danger-btn" (click)="confirming.set(true)">
                Delete my account
              </button>
            </div>
          } @else {
            <label class="field">
              <span>Type your password to confirm</span>
              <input type="password" autocomplete="current-password"
                [value]="deletePassword()" (input)="deletePassword.set(value($event))" />
            </label>
            @if (deleteError(); as message) {
              <p class="error" role="alert">{{ message }}</p>
            }
            <div class="right">
              <button type="button" class="ghost" (click)="cancelDelete()">Cancel</button>
              <button type="button" class="danger-btn"
                [disabled]="!deletePassword() || busy()" (click)="deleteAccount()">
                {{ busy() ? 'Deleting…' : 'Delete everything, permanently' }}
              </button>
            </div>
          }
        </div>
      </section>

      <p class="note">
        The language model, storage and privacy settings live in the server's
        <code>.env</code> file — this build has no per-account provider configuration yet.
      </p>
    </div>
  `,
  styles: [
    `
      /* .card and .card-header come from styles.css. Only layout here. */
      .page { padding: 28px; display: flex; flex-direction: column; gap: 20px; max-width: 720px; }

      .rows { padding: 8px 18px 18px; display: flex; flex-direction: column; gap: 4px; }
      .row { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 10px 0; }
      .row-info { display: flex; flex-direction: column; gap: 2px; }
      .row-label { font-size: 14px; font-weight: 500; }
      .row-desc { font-size: 12px; color: var(--text-tertiary); }

      .toggle {
        width: 44px; height: 24px; border-radius: 999px; flex: none;
        background: var(--border-light); transition: background .15s;
      }
      .toggle.active { background: var(--accent); }
      .toggle-knob {
        display: block; width: 18px; height: 18px; margin-left: 3px;
        border-radius: 50%; background: #fff; transition: transform .15s;
      }
      .toggle.active .toggle-knob { transform: translateX(20px); }

      .danger { font-size: 13px; font-weight: 600; color: var(--danger, #dc2626); }
      .note { margin: 0; font-size: 12px; color: var(--text-tertiary); }
      .note code { font-family: ui-monospace, monospace; }

      .form { gap: 10px; }
      .field { display: block; }
      .field > span {
        display: block; margin-bottom: 5px;
        font-size: 12px; font-weight: 600; color: var(--text-secondary);
      }
      .field input {
        width: 100%; max-width: 340px; padding: 8px 11px; font: inherit; font-size: 14px;
        border: 1px solid var(--border-light); border-radius: var(--radius);
        background: var(--bg-primary); color: var(--text-primary);
      }
      .hint { margin: 0; font-size: 12px; line-height: 1.6; color: var(--text-tertiary); }
      .hint code {
        font-family: ui-monospace, monospace; font-size: 11px;
        background: var(--bg-hover); padding: 1px 5px; border-radius: 4px;
      }
      .error { margin: 0; font-size: 13px; color: var(--danger, #dc2626); }
      .ok { margin: 0; font-size: 13px; color: var(--accent); }

      .right { display: flex; justify-content: flex-end; align-items: center; gap: 10px; margin-top: 4px; }
      .primary {
        padding: 8px 16px; border-radius: var(--radius); background: var(--accent);
        color: #fff; font-size: 13px; font-weight: 600;
      }
      .primary:disabled { opacity: .5; }
      .ghost { font-size: 13px; color: var(--text-secondary); padding: 8px 4px; }
      .ghost-btn {
        flex: none; padding: 8px 14px; border-radius: var(--radius);
        border: 1px solid var(--border-light); color: var(--text-primary);
        font-size: 13px; font-weight: 600;
      }
      .ghost-btn:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
      .ghost-btn:disabled { opacity: .5; }
      .danger-card { border-color: var(--danger, #dc2626); }
      .danger-btn {
        padding: 8px 16px; border-radius: var(--radius); font-size: 13px; font-weight: 600;
        color: #fff; background: var(--danger, #dc2626);
      }
      .danger-btn:disabled { opacity: .5; }

      @media (max-width: 768px) {
        .page { padding: 16px; }
      }
    `,
  ],
})
export class SettingsComponent {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  readonly auth = inject(AuthService);
  readonly theme = inject(ThemeService);

  readonly busy = signal(false);
  readonly currentPassword = signal('');
  readonly newPassword = signal('');
  readonly confirmPassword = signal('');
  readonly passwordError = signal<string | null>(null);

  readonly fullName = signal('');
  readonly nameError = signal<string | null>(null);
  readonly nameSaved = signal(false);

  readonly exporting = signal(false);
  readonly exportError = signal<string | null>(null);

  readonly confirming = signal(false);
  readonly deletePassword = signal('');
  readonly deleteError = signal<string | null>(null);

  /** Seeded once the account answers, so the field edits the name rather than replacing it. */
  private seeded = false;

  constructor() {
    effect(() => {
      const name = this.auth.fullName();
      if (!this.seeded && this.auth.userId() !== null) {
        this.seeded = true;
        this.fullName.set(name ?? '');
      }
    });
  }

  /** Only once both are typed: an empty second field is not yet a mismatch. */
  readonly mismatch = computed(
    () =>
      this.confirmPassword().length > 0 && this.newPassword() !== this.confirmPassword(),
  );

  /**
   * A typo here revokes every session, and there is no reset email to recover with —
   * which is why the confirmation is required rather than advisory.
   */
  readonly canChangePassword = computed(
    () =>
      this.currentPassword().length > 0 &&
      this.newPassword().length > 0 &&
      this.newPassword() === this.confirmPassword(),
  );

  value(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }

  /** Everything the account holds, assembled server-side so nothing is left out. */
  exportData(): void {
    this.exporting.set(true);
    this.exportError.set(null);
    this.http.get<unknown>(`${environment.apiUrl}/users/me/export`).subscribe({
      next: (data) => {
        this.exporting.set(false);
        download(
          new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }),
          `cv-pal-export-${new Date().toISOString().slice(0, 10)}.json`,
        );
      },
      error: (error: unknown) => {
        this.exporting.set(false);
        this.exportError.set(detailOf(error, 'That export could not be prepared.'));
      },
    });
  }

  /** Send the user back through setup. The flag is what keeps the redirect from firing. */
  rerunSetup(): void {
    const userId = this.auth.userId();
    if (userId !== null) {
      forgetWelcome(userId);
    }
    void this.router.navigate(['/welcome']);
  }

  saveName(): void {
    this.busy.set(true);
    this.nameError.set(null);
    this.nameSaved.set(false);
    this.auth.updateName(this.fullName().trim() || null).subscribe({
      next: () => {
        this.busy.set(false);
        this.nameSaved.set(true);
      },
      error: (error: unknown) => {
        this.busy.set(false);
        this.nameError.set(detailOf(error, 'That name could not be saved.'));
      },
    });
  }

  signOut(): void {
    this.auth.logout();
    void this.router.navigate(['/login']);
  }

  changePassword(): void {
    this.busy.set(true);
    this.passwordError.set(null);
    this.auth.changePassword(this.currentPassword(), this.newPassword()).subscribe({
      next: () => {
        this.busy.set(false);
        // The server has already revoked this session along with the others, so there
        // is nothing to log out from — only local tokens to stop carrying. The reason
        // travels with the redirect: without it a deliberate change is indistinguishable
        // from being signed out by something going wrong.
        this.auth.clearSession();
        void this.router.navigate(['/login'], {
          queryParams: { reason: 'password-changed' },
        });
      },
      error: (error: unknown) => {
        this.busy.set(false);
        this.passwordError.set(detailOf(error, 'That password could not be changed.'));
      },
    });
  }

  cancelDelete(): void {
    this.confirming.set(false);
    this.deletePassword.set('');
    this.deleteError.set(null);
  }

  deleteAccount(): void {
    const userId = this.auth.userId();
    this.busy.set(true);
    this.deleteError.set(null);
    this.auth.deleteAccount(this.deletePassword()).subscribe({
      next: () => {
        this.busy.set(false);
        this.auth.clearSession();
        // The account is gone, so its first-run flag goes with it — an id can be
        // reissued, and the next holder of it deserves the first run.
        if (userId !== null) {
          forgetWelcome(userId);
        }
        void this.router.navigate(['/login']);
      },
      error: (error: unknown) => {
        this.busy.set(false);
        this.deleteError.set(detailOf(error, 'The account could not be deleted.'));
      },
    });
  }
}

/** Save a blob under a filename. The anchor is the only way a browser offers. */
function download(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function detailOf(error: unknown, fallback: string): string {
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
