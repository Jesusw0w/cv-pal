import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AnalysisService } from '../../core/services/analysis.service';
import { ReviewService } from '../../core/services/review.service';
import { CvResponse, SuggestionResponse } from '../../shared/models/api.model';

/**
 * AI CV review — the one feature that needs a language model.
 *
 * **There is no chat endpoint** and no plan for one. The review the API performs
 * returns typed suggestions the user accepts or rejects, and this screen shows that:
 * mimicking a product we do not have is worse than showing the one we do.
 *
 * Everything else in CV Pal — parseability, keyword coverage, extraction, match scoring
 * — is deterministic and needs no model. This screen says so, because on a fresh install
 * with no provider configured it is the only screen that cannot work.
 */
@Component({
  selector: 'app-ai-tools',
  imports: [RouterLink],
  template: `
    <div class="page">
      <header class="intro">
        <h1>AI review</h1>
        <p>
          Suggestions on a CV's wording and structure, from the language model you configured. The
          <a routerLink="/analysis">parseability and keyword checks</a> need no model at all — start
          there if you have not set one up.
        </p>
      </header>

      @if (reviews.modelStatus.value(); as model) {
        @if (model.status === 'unavailable') {
          <p class="notice" role="status">
            {{ model.detail }} Reviews will fail until it is — with Ollama, run
            <code>ollama pull {{ model.model }}</code
            >, or check the model settings in <code>.env</code>.
          </p>
        }
      }

      <section class="card">
        <div class="card-header"><h3>Choose a CV</h3></div>
        @if (analysis.isLoading()) {
          <p class="muted body">Loading your CVs…</p>
        }
        <ul class="cv-list">
          @for (cv of analysis.documents(); track cv.id) {
            <li class="cv" [class.selected]="selected()?.id === cv.id">
              <button type="button" class="cv-pick" (click)="select(cv)">
                {{ cv.filename }}
              </button>
            </li>
          } @empty {
            @if (!analysis.isLoading()) {
              <li class="empty">
                No CVs yet. Upload one on the
                <a routerLink="/analysis">analysis screen</a>.
              </li>
            }
          }
        </ul>
      </section>

      @if (selected(); as cv) {
        <section class="card">
          <div class="card-header">
            <h3>{{ cv.filename }}</h3>
            <button type="button" class="primary" [disabled]="running()" (click)="analyseCv(cv)">
              {{
                running()
                  ? 'Reviewing…'
                  : suggestions().length > 0
                    ? 'Review again'
                    : 'Review this CV'
              }}
            </button>
          </div>

          @if (error(); as message) {
            <p class="error" role="alert">{{ message }}</p>
          }

          @if (loadingSuggestions()) {
            <p class="muted body">Loading previous suggestions…</p>
          }

          <ul class="suggestions">
            @for (item of suggestions(); track item.id) {
              <li class="suggestion" [class.decided]="item.accepted !== null">
                <span class="kind kind-{{ item.suggestion_type }}">{{ item.suggestion_type }}</span>
                <p class="text">{{ item.content }}</p>
                <div class="decide">
                  @if (item.accepted === null) {
                    <button type="button" class="yes" (click)="decide(item, true)">Useful</button>
                    <button type="button" class="no" (click)="decide(item, false)">
                      Not useful
                    </button>
                  } @else {
                    <span class="verdict">{{ item.accepted ? 'Marked useful' : 'Dismissed' }}</span>
                    <button type="button" class="undo" (click)="decide(item, !item.accepted)">
                      Change
                    </button>
                  }
                </div>
              </li>
            } @empty {
              @if (!running() && !loadingSuggestions()) {
                <li class="empty">No suggestions yet. Press <strong>Review this CV</strong>.</li>
              }
            }
          </ul>

          @if (suggestions().length > 0) {
            <p class="grounding">
              Marking a suggestion useful records your decision. It does not rewrite the file —
              nothing here edits a document on your behalf.
            </p>
          }
        </section>
      }
    </div>
  `,
  styles: [
    `
      .page {
        padding: 28px;
        display: flex;
        flex-direction: column;
        gap: 20px;
        max-width: 820px;
      }
      .intro a,
      .empty a {
        color: var(--accent);
        font-weight: 600;
      }

      .body {
        padding: 6px 18px 14px;
      }
      .muted {
        font-size: 13px;
        color: var(--text-tertiary);
        margin: 0;
      }
      .notice {
        margin: 0;
        padding: 12px 16px;
        border: 1px solid var(--border-light);
        border-left: 3px solid var(--danger, #dc2626);
        border-radius: var(--radius);
        font-size: 13px;
      }
      .error {
        margin: 0;
        padding: 6px 18px 12px;
        font-size: 13px;
        color: var(--danger, #dc2626);
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
        border-radius: var(--radius);
      }
      .cv:hover {
        background: var(--bg-hover);
      }
      .cv.selected {
        background: var(--bg-hover);
        box-shadow: inset 2px 0 0 var(--accent);
      }
      .cv-pick {
        width: 100%;
        text-align: left;
        padding: 9px 10px;
        font-size: 14px;
      }
      .empty {
        padding: 12px;
        font-size: 13px;
        color: var(--text-tertiary);
      }

      .suggestions {
        list-style: none;
        margin: 0;
        padding: 8px 18px 4px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .suggestion {
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding-bottom: 12px;
      }
      .suggestion + .suggestion {
        border-top: 1px solid var(--border-light);
        padding-top: 12px;
      }
      .suggestion.decided {
        opacity: 0.65;
      }
      .kind {
        align-self: flex-start;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        padding: 2px 8px;
        border-radius: 999px;
        border: 1px solid var(--border-light);
        color: var(--text-tertiary);
      }
      .text {
        margin: 0;
        font-size: 14px;
        color: var(--text-secondary);
        max-width: 78ch;
      }
      .decide {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .yes,
      .no,
      .undo {
        font-size: 12px;
        font-weight: 600;
      }
      .yes {
        color: #16a34a;
      }
      .no {
        color: var(--text-tertiary);
      }
      .undo {
        color: var(--accent);
      }
      .verdict {
        font-size: 12px;
        color: var(--text-tertiary);
      }

      .grounding {
        margin: 0;
        padding: 4px 18px 18px;
        font-size: 12px;
        color: var(--text-tertiary);
      }

      @media (max-width: 768px) {
      }
    `,
  ],
})
export class AiToolsComponent {
  readonly analysis = inject(AnalysisService);
  readonly reviews = inject(ReviewService);

  readonly selected = signal<CvResponse | null>(null);
  readonly suggestions = signal<SuggestionResponse[]>([]);
  readonly running = signal(false);
  readonly loadingSuggestions = signal(false);
  readonly error = signal<string | null>(null);

  select(cv: CvResponse): void {
    this.selected.set(cv);
    this.suggestions.set([]);
    this.error.set(null);

    // Load what a previous review already produced, so pressing Review again is a
    // choice rather than the only way to see anything.
    this.loadingSuggestions.set(true);
    this.reviews.suggestionsFor(cv.id).subscribe({
      next: (found) => {
        this.loadingSuggestions.set(false);
        this.suggestions.set(found);
      },
      error: () => this.loadingSuggestions.set(false),
    });
  }

  analyseCv(cv: CvResponse): void {
    this.running.set(true);
    this.error.set(null);
    this.reviews.analyse(cv.id).subscribe({
      next: (created) => {
        this.running.set(false);
        this.suggestions.update((existing) => [...created, ...existing]);
      },
      error: (error: unknown) => {
        this.running.set(false);
        this.error.set(messageFor(error));
      },
    });
  }

  decide(item: SuggestionResponse, accepted: boolean): void {
    this.reviews.decide(item.id, accepted).subscribe({
      next: (updated) =>
        this.suggestions.update((all) => all.map((one) => (one.id === updated.id ? updated : one))),
      error: (error: unknown) => this.error.set(messageFor(error)),
    });
  }
}

/**
 * The API's own message.
 *
 * This screen is the one that fails when no model is configured, and "the language model
 * is unavailable" tells the user exactly what to fix. A generic string would not.
 */
function messageFor(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    const detail = (error.error as { detail?: unknown } | null)?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
  }
  return 'The review could not be run.';
}
