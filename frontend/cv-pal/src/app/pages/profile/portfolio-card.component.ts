import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Observable } from 'rxjs';

import { CareerProfileService } from '../../core/services/career-profile.service';
import { detailOf } from '../../shared/http-error';

/**
 * Things the user made — a repository, a game, an illustration. General on purpose, so
 * it serves anyone whose work can be shown, not only developers.
 */
@Component({
  selector: 'app-portfolio-card',
  imports: [FormsModule],
  template: `
    <section class="card">
      <div class="card-header">
        <h3>Portfolio</h3>
        <span class="card-note">Projects, games, designs — anything you made</span>
      </div>
      <ul class="items">
        @for (item of career.profile().portfolio; track item.id) {
          <li>
            <div class="main">
              <strong>
                @if (item.url) {
                  <a [href]="link(item.url)" target="_blank" rel="noopener">{{ item.title }}</a>
                } @else {
                  {{ item.title }}
                }
              </strong>
              @if (item.description) {
                <span class="card-note">{{ item.description }}</span>
              }
            </div>
            <button
              type="button"
              class="remove"
              [attr.aria-label]="'Remove ' + item.title"
              (click)="remove(item.id)"
            >
              Remove
            </button>
          </li>
        } @empty {
          <li class="card-note">Nothing yet.</li>
        }
      </ul>
      <form class="add" (ngSubmit)="add()">
        <input name="title" placeholder="Title" maxlength="255" [(ngModel)]="title" />
        <input name="url" placeholder="Link (optional)" maxlength="512" [(ngModel)]="url" />
        <input
          name="description"
          class="wide"
          placeholder="One line on what it is (optional)"
          [(ngModel)]="description"
        />
        <button type="submit" class="primary" [disabled]="busy() || !title.trim()">Add</button>
      </form>
      @if (error(); as message) {
        <p class="error" role="alert">{{ message }}</p>
      }
    </section>
  `,
  styles: [
    `
      .items {
        list-style: none;
        margin: 0;
        padding: 0 18px;
      }
      .items li {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 12px;
        padding: 8px 0;
        font-size: 14px;
      }
      .main {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      .add {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding: 10px 18px 16px;
      }
      .add input {
        padding: 7px 10px;
        font: inherit;
        font-size: 14px;
        border: 1px solid var(--border-light);
        border-radius: var(--radius);
        background: var(--bg-primary);
        color: var(--text-primary);
      }
      .add .wide {
        flex: 1 1 260px;
      }
      .remove {
        flex: none;
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .error {
        margin: 0 18px 12px;
        font-size: 13px;
        color: var(--danger, #dc2626);
      }
    `,
  ],
})
export class PortfolioCardComponent {
  readonly career = inject(CareerProfileService);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);

  title = '';
  url = '';
  description = '';

  /** Links are often typed without a scheme; the browser needs one. */
  link(url: string): string {
    return /^https?:\/\//i.test(url) ? url : `https://${url}`;
  }

  add(): void {
    const payload = {
      title: this.title.trim(),
      url: this.url.trim() || null,
      description: this.description.trim() || null,
    };
    this.run(this.career.addPortfolioItem(payload), () => {
      this.title = '';
      this.url = '';
      this.description = '';
    });
  }

  remove(id: number): void {
    this.run(this.career.deletePortfolioItem(id));
  }

  private run(request: Observable<unknown>, onDone?: () => void): void {
    this.busy.set(true);
    this.error.set(null);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        onDone?.();
        this.career.reload();
      },
      error: (error: unknown) => {
        this.busy.set(false);
        this.error.set(detailOf(error, 'That could not be saved.'));
      },
    });
  }
}
