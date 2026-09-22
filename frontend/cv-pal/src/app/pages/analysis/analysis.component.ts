import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import {
  AnalysisService,
  MIN_JOB_DESCRIPTION_LENGTH,
  rejectUpload,
} from '../../core/services/analysis.service';
import {
  CoverageResponse,
  CvResponse,
  KeywordResponse,
  ParseabilityResponse,
} from '../../shared/models/api.model';

/**
 * The deterministic analysis, given a screen.
 *
 * Upload a CV, paste a posting, and get an ATS parseability report and a ranked list
 * of the terms the posting requires that the CV never says.
 *
 * **No language model is involved.** Nothing here needs an API key or a running Ollama,
 * which is what makes it the honest first screen for a fresh install.
 */
@Component({
  selector: 'app-analysis',
  imports: [FormsModule],
  template: `
    <div class="page">
      <header class="intro">
        <h1>CV analysis</h1>
        <p>
          Check whether a CV survives automated screening, and how well it answers a specific
          posting. Runs entirely on your machine — no language model needed.
        </p>
      </header>

      <section class="card">
        <div class="card-header">
          <h3>1. Choose a CV</h3>
          <label class="upload">
            <input
              type="file"
              accept=".pdf,.docx"
              (change)="onFileChosen($event)"
              [disabled]="uploading()"
            />
            {{ uploading() ? 'Uploading…' : 'Upload a CV' }}
          </label>
        </div>

        @if (uploadError(); as message) {
          <p class="error" role="alert">{{ message }}</p>
        }

        @if (analysis.error()) {
          <p class="error" role="alert">
            Could not load your CVs.
            <button type="button" class="link" (click)="analysis.reload()">Try again</button>
          </p>
        } @else if (analysis.isLoading()) {
          <p class="muted">Loading your CVs…</p>
        }

        <ul class="cv-list">
          @for (cv of analysis.documents(); track cv.id) {
            <li class="cv" [class.selected]="cv.id === selectedId()">
              <button type="button" class="cv-pick" (click)="select(cv)">
                <span class="cv-name">{{ cv.filename }}</span>
                <span class="cv-meta">version {{ cv.version }}</span>
              </button>
              <button
                type="button"
                class="cv-delete"
                [attr.aria-label]="'Delete ' + cv.filename"
                (click)="remove(cv)"
              >
                Delete
              </button>
            </li>
          } @empty {
            @if (!analysis.isLoading()) {
              <li class="empty">No CVs yet. Upload a PDF or DOCX to analyse it.</li>
            }
          }
        </ul>
      </section>

      <section class="card">
        <div class="card-header">
          <h3>2. Paste the job posting</h3>
          <span class="card-note">Optional — parseability works without one</span>
        </div>
        <textarea
          rows="8"
          [(ngModel)]="jobDescription"
          placeholder="Paste the full job description here, including the requirements list."
          aria-label="Job description"
        ></textarea>
        <div class="actions">
          <button
            type="button"
            class="primary"
            [disabled]="selectedId() === null || running()"
            (click)="run()"
          >
            {{ running() ? 'Analysing…' : 'Analyse' }}
          </button>
          @if (selectedId() === null) {
            <span class="muted">Choose a CV first.</span>
          } @else if (jobDescription.trim().length > 0 && !jobDescriptionIsUsable()) {
            <span class="muted">
              A posting needs at least {{ minJobDescription }} characters to score against.
            </span>
          }
        </div>
        @if (runError(); as message) {
          <p class="error" role="alert">{{ message }}</p>
        }
      </section>

      @if (parseability(); as report) {
        <section class="card">
          <div class="card-header">
            <h3>ATS parseability</h3>
            <span class="score" [class]="scoreTone(report.score)"
              >{{ report.score }}<small>/100</small></span
            >
          </div>
          <p class="muted detail">
            Whether an applicant tracking system can read this file at all.
            {{ report.word_count }} words extracted.
          </p>
          <ul class="findings">
            @for (finding of report.findings; track finding.code) {
              <li class="finding" [class]="'sev-' + finding.severity">
                <span class="sev-label">{{ finding.severity }}</span>
                <span>{{ finding.message }}</span>
              </li>
            } @empty {
              <li class="finding sev-info">
                <span>Nothing to fix — this file parses cleanly.</span>
              </li>
            }
          </ul>
        </section>
      }

      @if (coverage(); as report) {
        <section class="card">
          <div class="card-header">
            <h3>Keyword coverage</h3>
            <span class="score" [class]="scoreTone(report.score)"
              >{{ report.score }}<small>/100</small></span
            >
          </div>
          <p class="muted detail">
            How much of what this posting asks for the CV actually says. Weighted towards hard
            requirements.
          </p>

          @if (report.missing_required.length > 0) {
            <div class="group">
              <h4>Required, and missing</h4>
              <p class="group-note">Fix these first — each one is a stated requirement.</p>
              <div class="terms">
                @for (term of report.missing_required; track term.term) {
                  <span class="term missing-required">{{ term.term }}</span>
                }
              </div>
            </div>
          }

          @if (missingPreferred().length > 0) {
            <div class="group">
              <h4>Nice to have, and missing</h4>
              <div class="terms">
                @for (term of missingPreferred(); track term.term) {
                  <span class="term missing">{{ term.term }}</span>
                }
              </div>
            </div>
          }

          <div class="group">
            <h4>Already covered</h4>
            <div class="terms">
              @for (term of report.matched; track term.term) {
                <span class="term matched">{{ term.term }}</span>
              } @empty {
                <span class="muted">Nothing in this posting matched the CV.</span>
              }
            </div>
          </div>

          <p class="grounding">
            A missing term is only worth adding if it is true of you. CV Pal will not write in
            experience you do not have.
          </p>
        </section>
      }
    </div>
  `,
  styles: [
    `
      /* .card, .card-header come from styles.css. Only layout here. */
      .page {
        padding: 28px;
        display: flex;
        flex-direction: column;
        gap: 20px;
        max-width: 900px;
      }

      .intro p {
        margin: 0;
        font-size: 14px;
        color: var(--text-secondary);
        max-width: 70ch;
      }

      .cv-list {
        list-style: none;
        margin: 0;
        padding: 8px;
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      .cv {
        display: flex;
        align-items: center;
        gap: 8px;
        border-radius: var(--radius);
        padding: 4px 8px;
      }
      .cv:hover {
        background: var(--bg-hover);
      }
      .cv.selected {
        background: var(--bg-hover);
        box-shadow: inset 2px 0 0 var(--accent);
      }
      .cv-pick {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 2px;
        padding: 8px 4px;
        text-align: left;
      }
      .cv-name {
        font-size: 14px;
        font-weight: 500;
      }
      .cv-meta {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .cv-delete {
        font-size: 12px;
        color: var(--text-tertiary);
        padding: 6px;
      }
      .cv-delete:hover {
        color: var(--danger, #dc2626);
      }
      .empty {
        padding: 12px;
        font-size: 13px;
        color: var(--text-tertiary);
      }

      textarea {
        width: 100%;
        padding: 12px;
        border: 1px solid var(--border-light);
        border-radius: var(--radius);
        background: var(--bg-primary);
        color: var(--text-primary);
        font-size: 13px;
        font-family: inherit;
        resize: vertical;
      }
      .actions {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-top: 12px;
      }
      .primary {
        padding: 9px 18px;
        border-radius: var(--radius);
        background: var(--accent);
        color: #fff;
        font-size: 14px;
        font-weight: 600;
      }

      .score {
        font-size: 24px;
        font-weight: 700;
      }
      .score small {
        font-size: 13px;
        font-weight: 500;
        color: var(--text-tertiary);
      }
      .score.good {
        color: #16a34a;
      }
      .score.fair {
        color: #d97706;
      }
      .score.poor {
        color: var(--danger, #dc2626);
      }

      .detail {
        margin: 0 18px 4px;
      }
      .muted {
        font-size: 13px;
        color: var(--text-tertiary);
        margin: 0;
      }
      .error {
        margin: 0 18px 8px;
        font-size: 13px;
        color: var(--danger, #dc2626);
      }
      .link {
        color: var(--accent);
        font-weight: 600;
      }

      .findings {
        list-style: none;
        margin: 0;
        padding: 8px 18px 18px;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .finding {
        display: flex;
        gap: 10px;
        font-size: 13px;
        color: var(--text-secondary);
      }
      .sev-label {
        flex: none;
        min-width: 60px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        padding-top: 2px;
      }
      .sev-error .sev-label {
        color: var(--danger, #dc2626);
      }
      .sev-warning .sev-label {
        color: #d97706;
      }
      .sev-info .sev-label {
        color: var(--text-tertiary);
      }

      .group {
        padding: 0 18px 14px;
      }
      .group h4 {
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--text-tertiary);
        margin: 10px 0 6px;
      }
      .group-note {
        margin: 0 0 8px;
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .terms {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .term {
        font-size: 12px;
        padding: 3px 9px;
        border-radius: 999px;
        border: 1px solid var(--border-light);
      }
      .term.missing-required {
        border-color: color-mix(in srgb, var(--danger, #dc2626) 45%, transparent);
        color: var(--danger, #dc2626);
      }
      .term.missing {
        color: var(--text-secondary);
      }
      .term.matched {
        border-color: color-mix(in srgb, #16a34a 40%, transparent);
        color: #16a34a;
      }

      .grounding {
        margin: 0;
        padding: 0 18px 18px;
        font-size: 12px;
        color: var(--text-tertiary);
      }

      @media (max-width: 768px) {
      }
    `,
  ],
})
export class AnalysisComponent {
  readonly analysis = inject(AnalysisService);
  readonly minJobDescription = MIN_JOB_DESCRIPTION_LENGTH;

  readonly selectedId = signal<number | null>(null);
  readonly uploading = signal(false);
  readonly running = signal(false);
  readonly uploadError = signal<string | null>(null);
  readonly runError = signal<string | null>(null);
  readonly parseability = signal<ParseabilityResponse | null>(null);
  readonly coverage = signal<CoverageResponse | null>(null);

  jobDescription = '';

  /** `missing` includes the required ones; this is the remainder, shown separately. */
  readonly missingPreferred = computed<KeywordResponse[]>(
    () => this.coverage()?.missing.filter((term) => !term.required) ?? [],
  );

  jobDescriptionIsUsable(): boolean {
    return this.jobDescription.trim().length >= MIN_JOB_DESCRIPTION_LENGTH;
  }

  scoreTone(score: number): string {
    if (score >= 80) return 'good';
    return score >= 55 ? 'fair' : 'poor';
  }

  select(cv: CvResponse): void {
    this.selectedId.set(cv.id);
    // Results belong to the CV that produced them, so showing them against a different
    // one would be actively misleading.
    this.clearResults();
  }

  onFileChosen(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) {
      return;
    }
    // Let the same file be chosen again after a failure.
    input.value = '';

    const rejection = rejectUpload(file);
    if (rejection !== null) {
      this.uploadError.set(rejection);
      return;
    }

    this.uploading.set(true);
    this.uploadError.set(null);
    this.analysis.upload(file).subscribe({
      next: (cv) => {
        this.uploading.set(false);
        this.analysis.reload();
        this.select(cv);
      },
      error: (error: unknown) => {
        this.uploading.set(false);
        this.uploadError.set(messageFor(error, 'Could not upload that file.'));
      },
    });
  }

  remove(cv: CvResponse): void {
    this.analysis.delete(cv.id).subscribe({
      next: () => {
        if (this.selectedId() === cv.id) {
          this.selectedId.set(null);
          this.clearResults();
        }
        this.analysis.reload();
      },
      error: (error: unknown) =>
        this.uploadError.set(messageFor(error, 'Could not delete that CV.')),
    });
  }

  run(): void {
    const cvId = this.selectedId();
    if (cvId === null) {
      return;
    }

    this.running.set(true);
    this.runError.set(null);
    this.clearResults();

    this.analysis.checkParseability(cvId).subscribe({
      next: (report) => {
        this.parseability.set(report);
        if (this.jobDescriptionIsUsable()) {
          this.runCoverage(cvId);
        } else {
          this.running.set(false);
        }
      },
      error: (error: unknown) => this.fail(error),
    });
  }

  private runCoverage(cvId: number): void {
    this.analysis.checkCoverage(cvId, this.jobDescription.trim()).subscribe({
      next: (report) => {
        this.coverage.set(report);
        this.running.set(false);
      },
      error: (error: unknown) => this.fail(error),
    });
  }

  private fail(error: unknown): void {
    this.running.set(false);
    this.runError.set(messageFor(error, 'The analysis failed.'));
  }

  private clearResults(): void {
    this.parseability.set(null);
    this.coverage.set(null);
  }
}

/** The API's own message where there is one, so a 400 explains itself. */
function messageFor(error: unknown, fallback: string): string {
  if (error instanceof HttpErrorResponse) {
    const detail = (error.error as { detail?: unknown } | null)?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
  }
  return fallback;
}
