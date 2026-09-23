import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';

import { ApiTokenService } from '../../core/services/api-token.service';
import { ApiTokenCreatedResponse, ApiTokenResponse } from '../../shared/models/api.model';
import { detailOf } from '../../shared/http-error';

/** The lifetimes offered. The API caps a token at a year; there is no "never". */
const LIFETIMES = [30, 90, 365] as const;

/** What each scope lets an agent do, in the words the token list uses. */
const SCOPE_LABELS: Record<string, string> = {
  'cvpal:read': 'read',
  'cvpal:write': 'record applications',
  'cvpal:profile': 'edit profile',
};

/**
 * Agent access: personal access tokens for the MCP endpoint.
 *
 * The secret is shown once, right after creation, and never again — so the panel keeps
 * it on screen until the user dismisses it, rather than hiding it on the next reload.
 */
@Component({
  selector: 'app-agent-access',
  imports: [DatePipe],
  template: `
    <section class="card">
      <div class="card-header"><h3>Agent access (MCP)</h3></div>
      <div class="body">
        <p class="hint">
          Let an AI agent you run — Claude Desktop, Claude Code, or any MCP client — read your
          profile, score postings and tailor CVs, and, if you allow it, record applications or fill
          in your profile for you. Nothing it does sends an application.
        </p>

        @if (list(); as state) {
          @if (!state.mcp_enabled) {
            <p class="notice" role="status">
              This instance does not accept agents. Set <code>CV_PAL_MCP_ENABLED=true</code> in
              <code>.env</code> and restart to turn it on.
            </p>
          } @else {
            <p class="hint">
              Endpoint: <code>{{ tokens.endpoint }}</code>
            </p>
          }
        }

        @if (created(); as fresh) {
          <div class="secret" role="status">
            <p>
              <strong>Copy this token now.</strong> It will not be shown again. Give it to your
              agent as a bearer token.
            </p>
            <code class="token">{{ fresh.token }}</code>
            <div class="right">
              <button type="button" class="ghost-btn" (click)="copy(fresh.token)">
                {{ copied() ? 'Copied' : 'Copy' }}
              </button>
              <button type="button" class="ghost-btn" (click)="created.set(null)">Done</button>
            </div>
          </div>
        }

        <ul class="tokens">
          @for (token of list()?.tokens ?? []; track token.id) {
            <li class="token-row" [class.expired]="isExpired(token)">
              <div class="token-info">
                <span class="token-name">{{ token.name }}</span>
                <span class="token-meta">
                  cvp_{{ token.display_hint }}… · {{ permissions(token) }} ·
                  @if (isExpired(token)) {
                    expired
                  } @else {
                    expires {{ token.expires_at | date: 'mediumDate' }}
                  }
                  ·
                  {{
                    token.last_used_at
                      ? 'last used ' + (token.last_used_at | date: 'medium')
                      : 'never used'
                  }}
                </span>
              </div>
              <button type="button" class="danger" (click)="revoke(token)">Revoke</button>
            </li>
          } @empty {
            <li class="hint">No tokens yet.</li>
          }
        </ul>

        <div class="form">
          <label class="field">
            <span>Name</span>
            <input
              type="text"
              placeholder="e.g. Claude Desktop on my laptop"
              maxlength="64"
              [value]="name()"
              (input)="name.set(value($event))"
            />
          </label>
          <label class="check">
            <input type="checkbox" [checked]="write()" (change)="write.set(checked($event))" />
            <span>Also let it save postings and record applications</span>
          </label>
          <label class="check">
            <input
              type="checkbox"
              [checked]="editProfile()"
              (change)="editProfile.set(checked($event))"
            />
            <span>Also let it edit your profile and goals</span>
          </label>
          @if (editProfile()) {
            <p class="notice" role="note">
              The agent will be able to add, change and delete your roles, education and skills, and
              replace your goals. Every CV CV Pal generates is built from these, so a wrong entry
              ends up on a CV. CV Pal tells the agent to write only what you said or what your own
              documents say, but it cannot check — review your profile after the agent has been at
              it, and revoke the token when you are done.
            </p>
          }
          <label class="field">
            <span>Expires after</span>
            <select [value]="days()" (change)="days.set(+value($event))">
              @for (option of lifetimes; track option) {
                <option [value]="option">{{ option }} days</option>
              }
            </select>
          </label>
          <label class="field">
            <span>Your password</span>
            <input
              type="password"
              autocomplete="current-password"
              [value]="password()"
              (input)="password.set(value($event))"
            />
          </label>
          @if (error(); as message) {
            <p class="error" role="alert">{{ message }}</p>
          }
          <div class="right">
            <button
              type="button"
              class="primary"
              [disabled]="!canCreate() || busy()"
              (click)="create()"
            >
              {{ busy() ? 'Creating…' : 'Create token' }}
            </button>
          </div>
          <p class="hint">
            A token works only for the agent endpoint, not for signing in. Changing your password
            revokes every token.
          </p>
        </div>
      </div>
    </section>
  `,
  styles: [
    `
      .body {
        padding: 8px 18px 18px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .hint {
        margin: 0;
        font-size: 12px;
        line-height: 1.6;
        color: var(--text-tertiary);
      }
      code {
        font-family: ui-monospace, monospace;
        font-size: 11px;
        background: var(--bg-hover);
        padding: 1px 5px;
        border-radius: 4px;
        overflow-wrap: anywhere;
      }
      .notice {
        margin: 0;
        padding: 10px 14px;
        border-left: 3px solid var(--accent);
        background: var(--bg-hover);
        border-radius: var(--radius);
        font-size: 13px;
      }
      .secret {
        padding: 12px 14px;
        border: 1px solid var(--accent);
        border-radius: var(--radius);
        font-size: 13px;
      }
      .secret p {
        margin: 0 0 8px;
      }
      .token {
        display: block;
        padding: 8px;
        font-size: 12px;
      }
      .tokens {
        list-style: none;
        margin: 0;
        padding: 0;
      }
      .token-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        padding: 8px 0;
        border-bottom: 1px solid var(--border-light);
      }
      .token-row.expired {
        opacity: 0.6;
      }
      .token-info {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      .token-name {
        font-size: 14px;
        font-weight: 500;
      }
      .token-meta {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .form {
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      .field > span {
        display: block;
        margin-bottom: 5px;
        font-size: 12px;
        font-weight: 600;
        color: var(--text-secondary);
      }
      .field input,
      .field select {
        width: 100%;
        max-width: 340px;
        padding: 8px 11px;
        font: inherit;
        font-size: 14px;
        border: 1px solid var(--border-light);
        border-radius: var(--radius);
        background: var(--bg-primary);
        color: var(--text-primary);
      }
      .check {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
      }
      .error {
        margin: 0;
        font-size: 13px;
        color: var(--danger, #dc2626);
      }
      .right {
        display: flex;
        justify-content: flex-end;
        gap: 10px;
      }
      .danger {
        flex: none;
        font-size: 13px;
        font-weight: 600;
        color: var(--danger, #dc2626);
      }
      .ghost-btn {
        padding: 6px 12px;
        border-radius: var(--radius);
        border: 1px solid var(--border-light);
        font-size: 13px;
        font-weight: 600;
      }
    `,
  ],
})
export class AgentAccessComponent {
  readonly tokens = inject(ApiTokenService);
  readonly lifetimes = LIFETIMES;

  readonly list = computed(() => this.tokens.tokens.value());
  readonly name = signal('');
  readonly write = signal(false);
  readonly editProfile = signal(false);
  readonly days = signal<number>(90);
  readonly password = signal('');
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);
  readonly created = signal<ApiTokenCreatedResponse | null>(null);
  readonly copied = signal(false);

  readonly canCreate = computed(
    () =>
      this.list()?.mcp_enabled === true &&
      this.name().trim().length > 0 &&
      this.password().length > 0,
  );

  create(): void {
    this.busy.set(true);
    this.error.set(null);
    this.tokens
      .create({
        name: this.name().trim(),
        password: this.password(),
        write: this.write(),
        edit_profile: this.editProfile(),
        expires_in_days: this.days(),
      })
      .subscribe({
        next: (token) => {
          this.created.set(token);
          this.copied.set(false);
          this.name.set('');
          this.password.set('');
          this.write.set(false);
          this.editProfile.set(false);
          this.busy.set(false);
        },
        error: (error: unknown) => {
          this.error.set(detailOf(error, 'That token could not be created.'));
          this.busy.set(false);
        },
      });
  }

  revoke(token: ApiTokenResponse): void {
    this.tokens.revoke(token.id).subscribe({
      error: (error: unknown) =>
        this.error.set(detailOf(error, 'That token could not be revoked.')),
    });
  }

  copy(secret: string): void {
    void navigator.clipboard?.writeText(secret).then(() => this.copied.set(true));
  }

  /** "read, edit profile": what this token lets its agent do. */
  permissions(token: ApiTokenResponse): string {
    const scopes = token.scopes.split(' ');
    if (scopes.length === 1) {
      return 'read only';
    }
    return scopes.map((scope) => SCOPE_LABELS[scope] ?? scope).join(', ');
  }

  isExpired(token: ApiTokenResponse): boolean {
    return new Date(token.expires_at).getTime() <= Date.now();
  }

  value(event: Event): string {
    return (event.target as HTMLInputElement | HTMLSelectElement).value;
  }

  checked(event: Event): boolean {
    return (event.target as HTMLInputElement).checked;
  }
}
