import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { ApplicationService } from '../../core/services/application.service';
import { JobService } from '../../core/services/job.service';
import { ScoredPostingResponse } from '../../shared/models/api.model';
import { JobsComponent } from './jobs.component';

function scored(id: number, title: string, company: string): ScoredPostingResponse {
  return {
    posting: {
      id,
      source: 'manual',
      source_url: null,
      title,
      company,
      location: null,
      description: '',
      employment_type: null,
      created_at: '2026-07-01T00:00:00Z',
    },
    match: { score: 60, reasons: [], missing_required: [], blocked_by: null, preference_rank: 0 },
  };
}

describe('JobsComponent', () => {
  function render(appliedIds: number[] = []) {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        {
          provide: JobService,
          useValue: {
            matches: signal([
              scored(1, 'Backend Engineer', 'Globex'),
              scored(2, 'Data Analyst', 'Initech'),
            ]),
            blocked: signal([]),
            error: signal(undefined),
            isLoading: signal(false),
          },
        },
        {
          provide: ApplicationService,
          useValue: { appliedPostingIds: signal(new Set(appliedIds)) },
        },
      ],
    });
    const fixture = TestBed.createComponent(JobsComponent);
    fixture.detectChanges();

    const titles = () =>
      [...fixture.nativeElement.querySelectorAll('.job h3')].map((el: Element) => el.textContent);
    const set = (selector: string, change: (input: HTMLInputElement) => void, event: string) => {
      const input: HTMLInputElement = fixture.nativeElement.querySelector(selector);
      change(input);
      input.dispatchEvent(new Event(event));
      fixture.detectChanges();
    };
    return { fixture, titles, set };
  }

  it('filters postings by title or company, whatever the case', () => {
    const { titles, set } = render();
    expect(titles()).toEqual(['Backend Engineer', 'Data Analyst']);

    set('input[type=search]', (input) => (input.value = 'initech'), 'input');

    expect(titles()).toEqual(['Data Analyst']);
  });

  it('says the filter is why nothing shows, rather than that nothing is saved', () => {
    const { fixture, set } = render();

    set('input[type=search]', (input) => (input.value = 'no such role'), 'input');

    expect(fixture.nativeElement.textContent).toContain('Nothing matches that filter');
  });

  it('hides postings already applied for when asked to', () => {
    const { titles, set } = render([1]);

    set('input[type=checkbox]', (input) => (input.checked = true), 'change');

    expect(titles()).toEqual(['Data Analyst']);
  });
});
