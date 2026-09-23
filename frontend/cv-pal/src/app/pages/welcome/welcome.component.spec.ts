import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { WelcomeComponent } from './welcome.component';

describe('WelcomeComponent', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
  });

  // The first run is the first thing a new account sees, so a template that throws is
  // a blank page on the most important screen in the product.
  it('renders every step without throwing', () => {
    const fixture = TestBed.createComponent(WelcomeComponent);
    fixture.detectChanges();

    for (const step of [0, 1, 2, 3, 4]) {
      fixture.componentInstance.step.set(step);
      fixture.detectChanges();
      expect(fixture.nativeElement.querySelector('h2')).toBeTruthy();
    }
  });

  it('sends no salary floor when the field was left blank', () => {
    // A salary minimum is an integer on the API and an empty input is the string "" —
    // which Number() turns into 0, a floor of zero rather than no floor at all.
    const component = TestBed.createComponent(WelcomeComponent).componentInstance;

    expect(component.minSalary()).toBe('');
    expect(component.salaryFloor()).toBeNull();

    component.minSalary.set('55000');
    expect(component.salaryFloor()).toBe(55000);
  });

  it('sends no field for a step the user skipped', () => {
    // The wizard can be re-entered. Sending `headline: null` for an untouched field
    // would erase a headline the profile screen already holds, so a blank field must
    // leave the key out of the PATCH entirely.
    const fixture = TestBed.createComponent(WelcomeComponent);
    const http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    fixture.componentInstance.saveAboutYou();

    const patch = http.expectOne(
      (request) => request.method === 'PATCH' && request.url.endsWith('/profile'),
    );
    expect(patch.request.body).toEqual({});
  });
});
