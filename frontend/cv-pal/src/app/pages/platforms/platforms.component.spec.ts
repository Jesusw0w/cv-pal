import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { computed, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { PlatformService } from '../../core/services/platform.service';
import { JobPlatformResponse, JobPlatformUpdate } from '../../shared/models/api.model';
import { PlatformsComponent } from './platforms.component';

const BEHIND: JobPlatformResponse = {
  id: 1,
  name: 'Hired Hands',
  profile_url: 'hiredhands.example/sam',
  profile_updated_on: '2026-01-15',
  notes: null,
  status: 'outdated',
};

describe('PlatformsComponent', () => {
  let updates: [number, JobPlatformUpdate][];

  function render(platforms: JobPlatformResponse[]) {
    updates = [];
    const list = signal(platforms);
    TestBed.configureTestingModule({
      imports: [PlatformsComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: PlatformService,
          useValue: {
            platforms: list,
            error: signal(undefined),
            outdated: computed(() => list().filter((p) => p.status === 'outdated')),
            reload: () => undefined,
            update: (id: number, payload: JobPlatformUpdate) => {
              updates.push([id, payload]);
              return of(BEHIND);
            },
          },
        },
      ],
    });
    const fixture = TestBed.createComponent(PlatformsComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('says which platforms are behind the profile', () => {
    const fixture = render([BEHIND]);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('1 behind your profile');
    expect(text).toContain('Behind your profile');
  });

  it('records today when a platform is marked as updated', () => {
    const fixture = render([BEHIND]);

    fixture.componentInstance.markUpdated(BEHIND);

    expect(updates).toEqual([[1, { profile_updated_on: fixture.componentInstance.today }]]);
  });

  it('is optional: with nothing tracked it only offers to add one', () => {
    const fixture = render([]);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).not.toContain('Your platforms');
    expect(text).toContain('Add a platform');
  });
});
