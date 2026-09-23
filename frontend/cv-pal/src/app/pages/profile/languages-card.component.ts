import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Observable } from 'rxjs';

import { CareerProfileService } from '../../core/services/career-profile.service';
import { detailOf } from '../../shared/http-error';
import { LanguageLevel } from '../../shared/models/api.model';

const LEVELS: { value: LanguageLevel; label: string }[] = [
  { value: 'native', label: 'Native' },
  { value: 'fluent', label: 'Fluent' },
  { value: 'advanced', label: 'Advanced' },
  { value: 'intermediate', label: 'Intermediate' },
  { value: 'basic', label: 'Basic' },
];

/** Languages the user speaks. Printed on every generated CV; decisive for some roles. */
@Component({
  selector: 'app-languages-card',
  imports: [FormsModule],
  template: `
    <section class="card">
      <div class="card-header">
        <h3>Languages</h3>
        <span class="card-note">On every generated CV</span>
      </div>
      <ul class="items">
        @for (language of career.profile().languages; track language.id) {
          <li>
            <span
              ><strong>{{ language.name }}</strong> &middot; {{ label(language.level) }}</span
            >
            <button
              type="button"
              class="remove"
              [attr.aria-label]="'Remove ' + language.name"
              (click)="remove(language.id)"
            >
              Remove
            </button>
          </li>
        } @empty {
          <li class="card-note">No languages yet.</li>
        }
      </ul>
      <form class="add" (ngSubmit)="add()">
        <input name="language" placeholder="e.g. German" maxlength="64" [(ngModel)]="name" />
        <select name="level" [(ngModel)]="level" aria-label="Level">
          @for (option of levels; track option.value) {
            <option [value]="option.value">{{ option.label }}</option>
          }
        </select>
        <button type="submit" class="primary" [disabled]="busy() || !name.trim()">Add</button>
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
        align-items: center;
        padding: 6px 0;
        font-size: 14px;
      }
      .add {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding: 10px 18px 16px;
      }
      .add input,
      .add select {
        padding: 7px 10px;
        font: inherit;
        font-size: 14px;
        border: 1px solid var(--border-light);
        border-radius: var(--radius);
        background: var(--bg-primary);
        color: var(--text-primary);
      }
      .remove {
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
export class LanguagesCardComponent {
  readonly career = inject(CareerProfileService);
  readonly levels = LEVELS;
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);

  name = '';
  level: LanguageLevel = 'fluent';

  label(level: LanguageLevel): string {
    return LEVELS.find((option) => option.value === level)?.label ?? level;
  }

  add(): void {
    this.run(this.career.addLanguage({ name: this.name.trim(), level: this.level }), () => {
      this.name = '';
    });
  }

  remove(id: number): void {
    this.run(this.career.deleteLanguage(id));
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
