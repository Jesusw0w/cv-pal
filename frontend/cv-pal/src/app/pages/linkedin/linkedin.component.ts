import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { detailOf } from '../../shared/http-error';

import { ConfirmButtonComponent } from '../../shared/confirm-button.component';
import {
  LinkedInService,
  MIN_LINKEDIN_PASTE_LENGTH,
  rejectLinkedInFile,
} from '../../core/services/linkedin.service';

/**
 * The LinkedIn section: get the profile in, then see what it costs you as it stands.
 *
 * The screen states plainly that CV Pal does not fetch the profile, because a user who
 * expects it to will otherwise read the upload step as a missing feature rather than a
 * deliberate one: automated access is against LinkedIn's terms and the account it would
 * endanger is theirs.
 */
@Component({
  selector: 'app-linkedin',
  imports: [DatePipe, FormsModule, RouterLink, ConfirmButtonComponent],
  template: `
    <div class="page">
      <p class="intro">
        A section-by-section review of your LinkedIn profile, and a check that it agrees with your
        <a routerLink="/profile">career profile</a>.
      </p>

      @if (error(); as message) {
        <p class="error" role="alert">{{ message }}</p>
      }

      @if (linkedin.isLoading() && !linkedin.hasProfile()) {
        <p class="muted">Loading…</p>
      }

      <!-- Import. Shown above the review while there is nothing to review, and folded
           into a secondary card once there is. -->
      <section class="card">
        <div class="card-header">
          <h3>{{ linkedin.hasProfile() ? 'Import again' : 'Import your profile' }}</h3>
          <span class="card-note"> CV Pal never opens linkedin.com — you bring the copy. </span>
        </div>

        <p class="body muted">
          <strong>Print your profile to PDF</strong>: open it, expand every "see more", then Ctrl+P
          → Save as PDF. LinkedIn's own <em>Save to PDF</em> and the ZIP from a data export work
          too.
        </p>

        <div class="actions">
          <label class="upload">
            <input
              type="file"
              accept=".pdf,.zip"
              (change)="onFileChosen($event)"
              [disabled]="busy()"
            />
            {{ busy() ? 'Reading…' : 'Upload PDF or data export' }}
          </label>
          <button type="button" class="link" (click)="pasting.set(!pasting())">
            {{ pasting() ? 'Cancel paste' : 'Or paste it instead' }}
          </button>
        </div>

        @if (pasting()) {
          <div class="paste">
            <textarea
              rows="8"
              [(ngModel)]="pasted"
              placeholder="Select your whole profile page, copy, and paste it here."
              aria-label="Pasted LinkedIn profile"
            ></textarea>
            <button
              type="button"
              class="primary"
              [disabled]="pasted().trim().length < minPaste || busy()"
              (click)="submitPaste()"
            >
              Import pasted profile
            </button>
            <span class="muted small">
              Pasting loses the section boundaries, so the review scores only what it can recognise.
            </span>
          </div>
        }
      </section>

      @if (linkedin.profile(); as profile) {
        @if (linkedin.review(); as review) {
          <section class="card">
            <div class="score-head">
              <div>
                <span class="score-label">Profile review</span>
                <span class="score-value">{{ review.score }}<small>/100</small></span>
              </div>
              <span class="badge">{{ sourceLabel(review.source) }}</span>
            </div>
            <div
              class="score-bar"
              role="progressbar"
              [attr.aria-valuenow]="review.score"
              aria-valuemin="0"
              aria-valuemax="100"
            >
              <div class="score-fill" [style.width.%]="review.score"></div>
            </div>
            <p class="note">{{ review.note }}</p>

            <ul class="sections">
              @for (section of review.sections; track section.section) {
                <li class="section" [class]="section.status">
                  <span class="section-name">{{ label(section.section) }}</span>
                  <span class="section-detail">{{ section.detail }}</span>
                </li>
              }
            </ul>
          </section>

          <!-- The single most useful next step for a profile imported from a PDF: the
               PDF simply does not contain the skill list or the About text. -->
          @if (linkedin.wouldBenefitFromExport()) {
            <section class="card advice">
              <h3>Your import is missing data LinkedIn holds</h3>
              <p class="body">
                A profile PDF carries only your <strong>top three skills</strong>, no About section
                and no role descriptions — so parts of this review are scoring the export's limits
                rather than your profile. The official data export has all of it.
              </p>
              <p class="body muted">
                <strong
                  >Me → Settings &amp; Privacy → Data Privacy → Get a copy of your data.</strong
                >
                Pick Profile, Positions, Education and Skills. LinkedIn takes up to 72 hours, then
                upload the ZIP here — it fills in what is missing and leaves everything else alone.
              </p>
            </section>
          }

          @if (review.coverage; as coverage) {
            <section class="card">
              <div class="card-header">
                <h3>Recruiter search coverage</h3>
                <span class="card-note">{{ coverage.score }}% against your target roles</span>
              </div>
              @if (coverage.missing.length > 0) {
                <p class="body muted">
                  Not evidenced anywhere a recruiter searches — your headline, About or skills:
                </p>
                <ul class="terms">
                  @for (keyword of coverage.missing.slice(0, 12); track keyword.term) {
                    <li class="term" [class.required]="keyword.required">{{ keyword.term }}</li>
                  }
                </ul>
              } @else {
                <p class="body muted">Every term from your target roles appears.</p>
              }
            </section>
          } @else {
            <section class="card">
              <p class="body muted">
                Set your <a routerLink="/profile/goals">target roles</a> and this screen will also
                score how findable the profile is in recruiter search.
              </p>
            </section>
          }

          <section class="card">
            <div class="card-header">
              <h3>Agreement with your career profile</h3>
              <span class="card-note"> {{ review.consistency.length }} difference(s) </span>
            </div>
            @if (review.consistency.length === 0) {
              <p class="body muted">The two records agree on every employer, title and date.</p>
            } @else {
              <p class="body muted">
                A recruiter can see both. CV Pal does not change either — which one is right is your
                call.
              </p>
              <ul class="issues">
                @for (issue of review.consistency; track issue.detail) {
                  <li class="issue">{{ issue.detail }}</li>
                }
              </ul>
            }
          </section>

          <section class="card">
            <div class="card-header">
              <h3>What was imported</h3>
              <span class="card-note">
                {{ profile.imported_at | date: 'd MMM y, HH:mm' }}
              </span>
            </div>
            <dl class="facts">
              <dt>Name</dt>
              <dd>{{ profile.full_name ?? '—' }}</dd>
              <dt>Headline</dt>
              <dd>{{ profile.headline ?? '—' }}</dd>
              <dt>Roles</dt>
              <dd>{{ profile.positions.length }}</dd>
              <dt>Education</dt>
              <dd>{{ profile.educations.length }}</dd>
              <dt>Skills</dt>
              <dd>{{ profile.skills.length }}</dd>
            </dl>
            <app-confirm-button
              class="body"
              label="Delete the imported profile"
              (confirmed)="remove()"
              >Delete imported profile</app-confirm-button
            >
          </section>
        }
      }
    </div>
  `,
  styles: [
    `
      /* Cards here are padded as a whole, so their headers and bodies are not. */
      .card {
        padding: 18px 20px;
      }
      .card-header {
        padding: 0 0 12px;
        margin-bottom: 12px;
        align-items: baseline;
        gap: 12px;
      }
      .body {
        padding: 0;
        margin-bottom: 10px;
        font-size: 13px;
        max-width: 72ch;
      }
      .muted {
        color: var(--text-secondary);
      }
      .small {
        font-size: 12px;
      }

      .actions {
        display: flex;
        align-items: center;
        gap: 16px;
        flex-wrap: wrap;
      }

      .paste {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-top: 12px;
      }

      .score-head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
      }
      .score-label {
        font-size: 13px;
        font-weight: 600;
        margin-right: 10px;
      }
      .score-value {
        font-size: 20px;
        font-weight: 700;
      }
      .score-value small {
        font-size: 12px;
        font-weight: 500;
        color: var(--text-tertiary);
      }
      .badge {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: var(--text-tertiary);
      }
      .score-bar {
        height: 6px;
        border-radius: 3px;
        background: var(--border);
        overflow: hidden;
        margin: 8px 0;
      }
      .score-fill {
        height: 100%;
        background: var(--accent);
      }
      .note {
        margin: 0 0 12px;
        font-size: 12px;
        color: var(--text-tertiary);
        max-width: 72ch;
      }

      .sections {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .section {
        display: flex;
        gap: 12px;
        font-size: 13px;
        padding-left: 10px;
        border-left: 3px solid var(--border);
      }
      .section.missing {
        border-left-color: var(--danger);
      }
      .section.thin {
        border-left-color: var(--warning);
      }
      .section.ok {
        border-left-color: var(--success);
      }
      .section-name {
        font-weight: 600;
        min-width: 90px;
      }
      .section-detail {
        color: var(--text-secondary);
      }

      .advice h3 {
        font-size: 15px;
        margin: 0 0 8px;
      }

      .issues {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .issue {
        font-size: 13px;
        color: var(--text-secondary);
        padding-left: 10px;
        border-left: 3px solid var(--warning);
      }

      .facts {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 4px 16px;
        margin: 0 0 12px;
        font-size: 13px;
      }
      .facts dt {
        color: var(--text-tertiary);
      }
      .facts dd {
        margin: 0;
      }
    `,
  ],
})
export class LinkedInComponent {
  readonly linkedin = inject(LinkedInService);

  readonly busy = signal(false);
  readonly error = signal<string | null>(null);
  readonly pasting = signal(false);
  readonly pasted = signal('');
  readonly minPaste = MIN_LINKEDIN_PASTE_LENGTH;

  private readonly labels: Record<string, string> = {
    headline: 'Headline',
    about: 'About',
    experience: 'Experience',
    education: 'Education',
    skills: 'Skills',
  };

  label(section: string): string {
    return this.labels[section] ?? section;
  }

  sourceLabel(source: string): string {
    return { pdf: 'from PDF', export: 'from data export', paste: 'from paste' }[source] ?? source;
  }

  onFileChosen(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) {
      return;
    }
    input.value = '';

    const rejection = rejectLinkedInFile(file);
    if (rejection !== null) {
      this.error.set(rejection);
      return;
    }

    this.run(() => this.linkedin.upload(file), 'Could not read that file.');
  }

  submitPaste(): void {
    const text = this.pasted().trim();
    this.run(
      () => this.linkedin.paste(text),
      'Could not read that text.',
      () => {
        this.pasting.set(false);
        this.pasted.set('');
      },
    );
  }

  remove(): void {
    this.run(() => this.linkedin.delete(), 'Could not delete the imported profile.');
  }

  private run(
    action: () => { subscribe: (o: object) => unknown },
    fallback: string,
    onDone?: () => void,
  ): void {
    this.busy.set(true);
    this.error.set(null);
    action().subscribe({
      next: () => {
        this.busy.set(false);
        onDone?.();
        this.linkedin.reload();
      },
      error: (error: unknown) => {
        this.busy.set(false);
        this.error.set(detailOf(error, fallback));
      },
    });
  }
}
