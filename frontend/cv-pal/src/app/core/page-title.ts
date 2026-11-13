import { Injectable, inject, signal } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { RouterStateSnapshot, TitleStrategy } from '@angular/router';

/**
 * Names the browser tab after the screen ("Jobs · CV Pal") and keeps the same name
 * for the topbar, so the two cannot disagree and no page has to set either.
 */
@Injectable({ providedIn: 'root' })
export class PageTitleStrategy extends TitleStrategy {
  private readonly document = inject(Title);

  readonly current = signal('');

  override updateTitle(snapshot: RouterStateSnapshot): void {
    const title = this.buildTitle(snapshot) ?? '';
    this.current.set(title);
    this.document.setTitle(title ? `${title} · CV Pal` : 'CV Pal');
  }
}
