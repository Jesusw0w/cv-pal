import { Component, input, output, signal } from '@angular/core';

/**
 * A button for something that cannot be undone: the first press arms it, the second
 * confirms. Moving focus away disarms it, so a stray click never deletes anything.
 */
@Component({
  selector: 'app-confirm-button',
  template: `
    <button
      type="button"
      class="remove"
      [class.armed]="armed()"
      [disabled]="disabled()"
      [attr.aria-label]="armed() ? 'Confirm: ' + label() : label()"
      (click)="press()"
      (blur)="armed.set(false)"
    >
      @if (armed()) {
        Confirm?
      } @else {
        <ng-content>Delete</ng-content>
      }
    </button>
  `,
  styles: `
    :host {
      flex: none;
    }
    .armed {
      color: var(--danger);
      font-weight: 600;
    }
  `,
})
export class ConfirmButtonComponent {
  /** What is being removed, for screen readers: "Delete cv.pdf". */
  readonly label = input.required<string>();
  readonly disabled = input(false);
  readonly confirmed = output();

  protected readonly armed = signal(false);

  protected press(): void {
    if (this.armed()) {
      this.armed.set(false);
      this.confirmed.emit();
    } else {
      this.armed.set(true);
    }
  }
}
