import { TestBed } from '@angular/core/testing';

import { ConfirmButtonComponent } from './confirm-button.component';

describe('ConfirmButtonComponent', () => {
  function render() {
    const fixture = TestBed.createComponent(ConfirmButtonComponent);
    fixture.componentRef.setInput('label', 'Delete cv.pdf');
    const confirmed = vi.fn();
    fixture.componentInstance.confirmed.subscribe(confirmed);
    fixture.detectChanges();
    const button: HTMLButtonElement = fixture.nativeElement.querySelector('button');
    const press = () => {
      button.click();
      fixture.detectChanges();
    };
    return { fixture, button, confirmed, press };
  }

  it('does nothing irreversible on the first press', () => {
    const { button, confirmed, press } = render();

    press();

    expect(confirmed).not.toHaveBeenCalled();
    expect(button.textContent).toContain('Confirm?');
    expect(button.getAttribute('aria-label')).toBe('Confirm: Delete cv.pdf');
  });

  it('confirms on the second press', () => {
    const { confirmed, press } = render();

    press();
    press();

    expect(confirmed).toHaveBeenCalledOnce();
  });

  it('disarms when focus leaves, so a later stray click starts over', () => {
    const { fixture, button, confirmed, press } = render();

    press();
    button.dispatchEvent(new Event('blur'));
    fixture.detectChanges();
    press();

    expect(confirmed).not.toHaveBeenCalled();
  });
});
