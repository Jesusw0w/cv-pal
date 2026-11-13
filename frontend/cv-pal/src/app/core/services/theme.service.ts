import { Injectable, signal } from '@angular/core';

const STORAGE_KEY = 'theme';

/**
 * Light or dark. Follows the system until the user chooses, then remembers the choice.
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  readonly dark = signal(
    (localStorage.getItem(STORAGE_KEY) ??
      (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')) === 'dark',
  );

  constructor() {
    this.apply();
  }

  toggle(): void {
    this.dark.update((dark) => !dark);
    // Only a choice is stored: writing the system default back on load would pin it,
    // and the app would stop following the system the first time it was opened.
    localStorage.setItem(STORAGE_KEY, this.theme());
    this.apply();
  }

  private theme(): 'dark' | 'light' {
    return this.dark() ? 'dark' : 'light';
  }

  private apply(): void {
    document.documentElement.dataset['theme'] = this.theme();
  }
}
