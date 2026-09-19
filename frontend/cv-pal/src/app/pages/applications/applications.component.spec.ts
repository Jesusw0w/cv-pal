import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { ApplicationsComponent } from './applications.component';

describe('ApplicationsComponent', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
  });

  it('renders with nothing recorded', () => {
    // The state every new account is in, and the one an empty-state bug hides in.
    const fixture = TestBed.createComponent(ApplicationsComponent);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('h1').textContent).toContain(
      'Applications',
    );
    expect(fixture.nativeElement.textContent).toContain('Nothing recorded yet');
  });

  it('shows a dash rather than 0% before anything could have been answered', () => {
    // 0% and "no rate yet" are different claims about a search, and the first one is a
    // lie to anybody who applied this morning.
    const fixture = TestBed.createComponent(ApplicationsComponent);
    fixture.detectChanges();

    const rate: string = fixture.nativeElement.querySelector('.rate-value').textContent;
    expect(rate).not.toContain('0%');
    expect(fixture.nativeElement.textContent).toContain(
      'Nothing has been out long enough',
    );
  });

  it('records an application against the posting it is for', () => {
    const fixture = TestBed.createComponent(ApplicationsComponent);
    const http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    fixture.componentInstance.record(7);

    const posted = http.expectOne(
      (request) => request.method === 'POST' && request.url.endsWith('/applications'),
    );
    expect(posted.request.body).toEqual({ job_posting_id: 7 });
  });
});
