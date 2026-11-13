import { Component, computed, inject, input, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';

import { AnalysisService, MIN_JOB_DESCRIPTION_LENGTH } from '../../core/services/analysis.service';
import { JobService } from '../../core/services/job.service';
import { detailOf } from '../../shared/http-error';

/**
 * The deterministic checks on one CV: can an ATS read it, and does it say what a
 * posting asks for. No language model is involved, so both run as soon as there is
 * something to run them on.
 */
@Component({
  selector: 'app-cv-check',
  imports: [FormsModule],
  template: `
    <section class="card" [attr.aria-busy]="report.isLoading()">
      <div class="card-header">
        <h3>Can an ATS read it?</h3>
        @if (report.hasValue() && report.value(); as result) {
          <span class="score" [class]="tone(result.score)"
            >{{ result.score }}<small>/100</small></span
          >
        }
      </div>
      @if (report.isLoading()) {
        <p class="notice"><span class="spinner"></span> Reading the file…</p>
      } @else if (report.error(); as error) {
        <p class="error body" role="alert">{{ message(error) }}</p>
      } @else if (report.hasValue() && report.value(); as result) {
        <ul class="findings body">
          @for (finding of result.findings; track finding.code) {
            <li [class]="finding.severity">
              <strong>{{ finding.severity }}</strong>
              {{ finding.message }}
            </li>
          } @empty {
            <li>Nothing to fix — {{ result.word_count }} words read cleanly.</li>
          }
        </ul>
      }
    </section>

    <section class="card" [attr.aria-busy]="coverage.isLoading()">
      <div class="card-header">
        <h3>Does it answer a posting?</h3>
        @if (coverage.hasValue() && coverage.value(); as result) {
          <span class="score" [class]="tone(result.score)"
            >{{ result.score }}<small>/100</small></span
          >
        }
      </div>
      <div class="body compare">
        <!-- A saved posting needs no retyping; pasting stays for one not worth saving. -->
        <select [(ngModel)]="postingId" aria-label="Posting to compare against">
          <option [ngValue]="null">Paste a posting…</option>
          @for (entry of postings(); track entry.posting.id) {
            <option [ngValue]="entry.posting.id">
              {{ entry.posting.title }}
              @if (entry.posting.company) {
                — {{ entry.posting.company }}
              }
            </option>
          }
        </select>
        @if (postingId() === null) {
          <textarea
            rows="6"
            [(ngModel)]="pasted"
            placeholder="Paste the full job description, including the requirements list."
            aria-label="Job description"
          ></textarea>
          <button
            type="button"
            class="primary"
            [disabled]="pasted().trim().length < minLength"
            (click)="submitted.set(pasted().trim())"
          >
            Check coverage
          </button>
        }
        @if (coverage.isLoading()) {
          <p class="muted"><span class="spinner"></span> Comparing…</p>
        } @else if (coverage.error(); as error) {
          <p class="error" role="alert">{{ message(error) }}</p>
        } @else if (coverage.hasValue() && coverage.value(); as result) {
          @if (result.missing_required.length > 0) {
            <h4>Required, and missing</h4>
            <ul class="terms">
              @for (term of result.missing_required; track term.term) {
                <li class="term required">{{ term.term }}</li>
              }
            </ul>
          }
          @if (missingPreferred().length > 0) {
            <h4>Nice to have, and missing</h4>
            <ul class="terms">
              @for (term of missingPreferred(); track term.term) {
                <li class="term">{{ term.term }}</li>
              }
            </ul>
          }
          <h4>Covered</h4>
          <ul class="terms">
            @for (term of result.matched; track term.term) {
              <li class="term matched">{{ term.term }}</li>
            } @empty {
              <li class="muted">Nothing this posting asks for appears in the CV.</li>
            }
          </ul>
          <p class="hint">A missing term is only worth adding if it is true of you.</p>
        }
      </div>
    </section>
  `,
  styles: `
    :host {
      display: contents;
    }
    .findings {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 8px;
      font-size: 13px;
      color: var(--text-secondary);
    }
    .findings strong {
      display: inline-block;
      min-width: 64px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-tertiary);
    }
    .findings .error strong {
      color: var(--danger);
    }
    .findings .warning strong {
      color: var(--warning);
    }
    .compare {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 10px;
    }
    .compare select {
      max-width: 100%;
    }
    h4 {
      margin-top: 4px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--text-tertiary);
    }
    .spinner {
      display: inline-block;
      vertical-align: -2px;
      margin-right: 6px;
    }
  `,
})
export class CvCheckComponent {
  private readonly analysis = inject(AnalysisService);
  private readonly jobs = inject(JobService);

  readonly cvId = input.required<number>();

  protected readonly minLength = MIN_JOB_DESCRIPTION_LENGTH;

  protected readonly report = rxResource({
    params: () => this.cvId(),
    stream: ({ params }) => this.analysis.checkParseability(params),
  });

  /** A saved posting to compare against, or null to paste one. */
  protected readonly postingId = signal<number | null>(null);
  protected readonly pasted = signal('');
  /** The pasted text as last submitted, so typing does not fire a request per key. */
  protected readonly submitted = signal('');

  /** Saved postings with enough text to score against. */
  protected readonly postings = computed(() =>
    this.jobs
      .all()
      .filter((entry) => entry.posting.description.length >= MIN_JOB_DESCRIPTION_LENGTH),
  );

  private readonly description = computed(() => {
    const id = this.postingId();
    return id === null
      ? this.submitted()
      : (this.postings().find((entry) => entry.posting.id === id)?.posting.description ?? '');
  });

  /** Keyed on the CV as well, so a result is never shown against a different file. */
  protected readonly coverage = rxResource({
    params: () => {
      const description = this.description();
      return description.length >= MIN_JOB_DESCRIPTION_LENGTH
        ? { cvId: this.cvId(), description }
        : undefined;
    },
    stream: ({ params }) => this.analysis.checkCoverage(params.cvId, params.description),
  });

  /** `missing` includes the required ones; this is the remainder, shown separately. */
  protected readonly missingPreferred = computed(() =>
    this.coverage.hasValue()
      ? (this.coverage.value()?.missing ?? []).filter((t) => !t.required)
      : [],
  );

  protected tone(score: number): string {
    if (score >= 80) return 'good';
    return score >= 55 ? 'fair' : 'poor';
  }

  protected message(error: unknown): string {
    return detailOf(error, 'That check could not be run.');
  }
}
