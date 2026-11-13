import { Component, inject, input } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';

import { ReviewService } from '../../core/services/review.service';
import { Action } from '../../shared/action';
import { SuggestionResponse } from '../../shared/models/api.model';
import { valueOr } from '../../shared/resource';

/**
 * Suggestions on one CV from the configured language model — the only part of this
 * screen that needs one, so it says up front when there is none.
 *
 * A suggestion is marked useful or not; nothing here rewrites the file.
 */
@Component({
  selector: 'app-cv-review',
  template: `
    <section class="card">
      <div class="card-header">
        <h3>AI review</h3>
        <button type="button" class="primary" [disabled]="action.busy()" (click)="review()">
          {{ action.busy() ? 'Reviewing…' : list().length ? 'Review again' : 'Review' }}
        </button>
      </div>

      @if (reviews.modelProblem(); as model) {
        <p class="notice" role="status">
          {{ model.detail }} The checks above need no model; this one does. With Ollama, run
          <code>ollama pull {{ model.model }}</code
          >, or set the model in <code>.env</code>.
        </p>
      }
      @if (action.error(); as message) {
        <p class="error body" role="alert">{{ message }}</p>
      }

      <ul class="rows">
        @for (item of list(); track item.id) {
          <li class="row" [class.decided]="item.accepted !== null">
            <div class="row-main">
              <span class="row-meta kind">{{ item.suggestion_type }}</span>
              <p>{{ item.content }}</p>
            </div>
            @if (item.accepted === null) {
              <button type="button" class="link" (click)="decide(item, true)">Useful</button>
              <button type="button" class="remove" (click)="decide(item, false)">Dismiss</button>
            } @else {
              <span class="muted">{{ item.accepted ? 'Useful' : 'Dismissed' }}</span>
              <button type="button" class="remove" (click)="decide(item, !item.accepted)">
                Change
              </button>
            }
          </li>
        } @empty {
          @if (!suggestions.isLoading() && !reviews.modelProblem()) {
            <li class="empty">Wording and structure suggestions, from the model you configured.</li>
          }
        }
      </ul>
    </section>
  `,
  styles: `
    .row {
      align-items: flex-start;
    }
    .row p {
      font-size: 14px;
      color: var(--text-secondary);
      max-width: 78ch;
    }
    .kind {
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .decided {
      opacity: 0.65;
    }
    .rows:empty {
      display: none;
    }
  `,
})
export class CvReviewComponent {
  protected readonly reviews = inject(ReviewService);
  protected readonly action = new Action();

  readonly cvId = input.required<number>();

  /** What earlier reviews produced, so reviewing again is a choice, not the only way in. */
  protected readonly suggestions = rxResource({
    params: () => this.cvId(),
    stream: ({ params }) => this.reviews.suggestionsFor(params),
    defaultValue: [],
  });

  protected readonly list = valueOr(this.suggestions, []);

  protected review(): void {
    this.action.run(this.reviews.analyse(this.cvId()), 'The review could not be run.', (created) =>
      this.suggestions.set([...created, ...this.list()]),
    );
  }

  protected decide(item: SuggestionResponse, accepted: boolean): void {
    this.action.run(this.reviews.decide(item.id, accepted), 'That could not be saved.', (updated) =>
      this.suggestions.set(this.list().map((one) => (one.id === updated.id ? updated : one))),
    );
  }
}
