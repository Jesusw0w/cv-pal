import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { MOCK_CAREER_PROFILE } from '../../../mocks/fixtures/api.fixtures';
import { AuthService } from './auth.service';
import { CareerProfileService } from './career-profile.service';

describe('CareerProfileService', () => {
  let service: CareerProfileService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(CareerProfileService);
    http = TestBed.inject(HttpTestingController);

    // The resource stays idle until there is a session, so this fails if the profile
    // ever starts fetching while signed out.
    TestBed.inject(AuthService).login('dev@cvpal.test', 'a-long-enough-password').subscribe();
    http
      .expectOne((request) => request.url.endsWith('/auth/login'))
      .flush({ access_token: 'access-1', refresh_token: 'refresh-1', token_type: 'bearer' });

    // Signing in also loads the account for the sidebar; answer it so `verify()` in
    // `afterEach` is checking this service's requests rather than that one.
    TestBed.tick();
    for (const request of http.match((r) => r.url.endsWith('/users/me'))) {
      request.flush({
        id: 1,
        email: 'dev@cvpal.test',
        full_name: 'Dev User',
        is_active: true,
        created_at: '2026-01-15T10:00:00Z',
      });
    }

    // Reading the resource is what starts the request; flush the seeded profile so the
    // derived signals below are computed from a real `GET /profile` body.
    service.profile();
    TestBed.tick();
    http.expectOne((request) => request.url.endsWith('/profile')).flush(MOCK_CAREER_PROFILE);
    TestBed.tick();
  });

  afterEach(() => http.verify());

  it('scores completeness consistently with the gaps it lists', () => {
    // The score is derived from `gaps`, so a check added to one and not the other
    // would show up here as a score that no longer reaches 100 with an empty list.
    const gaps = service.gaps().length;
    const completeness = service.completeness();

    expect(completeness).toBeGreaterThanOrEqual(0);
    expect(completeness).toBeLessThanOrEqual(100);
    expect(gaps === 0).toBe(completeness === 100);
  });

  it('reports a skill with no role behind it as unevidenced', () => {
    // This is what stops a generated CV claiming experience the user cannot defend.
    for (const skill of service.ungroundedSkills()) {
      expect(skill.evidence_experience_ids.length).toBe(0);
      expect(skill.is_evidenced).toBe(false);
    }
    expect(service.ungroundedSkills().length).toBeGreaterThan(0);
  });

  it('lists experience newest first', () => {
    const dates = service.experiences().map((role) => role.start_date);
    expect([...dates].sort((a, b) => b.localeCompare(a))).toEqual(dates);
  });

  it('puts evidenced skills above unevidenced ones within a category', () => {
    for (const group of service.skillsByCategory()) {
      const evidenced = group.skills.map((skill) => Number(skill.is_evidenced));
      expect([...evidenced].sort((a, b) => b - a)).toEqual(evidenced);
    }
  });
});

describe('CareerProfileService writes', () => {
  let service: CareerProfileService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(CareerProfileService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('patches only the profile fields it is given', () => {
    service.updateProfile({ headline: 'Backend Engineer', summary: null }).subscribe();

    const request = http.expectOne((r) => r.url.endsWith('/profile'));
    expect(request.request.method).toBe('PATCH');
    // null clears a field; omitting it leaves it alone. Sending "" instead would store a
    // blank headline that reads as set but renders as nothing.
    expect(request.request.body).toEqual({ headline: 'Backend Engineer', summary: null });
    request.flush({});
  });

  it('creates a role without an end date for a current one', () => {
    service
      .addExperience({
        organisation: 'Acme',
        title: 'Engineer',
        start_date: '2021-03-01',
        end_date: null,
      })
      .subscribe();

    const request = http.expectOne((r) => r.url.endsWith('/profile/experiences'));
    expect(request.request.body.end_date).toBeNull();
    request.flush({});
  });

  it('reads a CV through the import endpoint, which stores nothing', () => {
    service.importFromCv(4).subscribe();

    const request = http.expectOne((r) => r.url.endsWith('/profile/import-from-cv/4'));
    expect(request.request.method).toBe('POST');
    request.flush({ contact: {}, experiences: [], educations: [], skills: [] });
  });

  it('deletes by id on the matching collection', () => {
    service.deleteSkill(9).subscribe();

    const request = http.expectOne((r) => r.url.endsWith('/profile/skills/9'));
    expect(request.request.method).toBe('DELETE');
    request.flush(null);
  });
});

describe('CareerProfileService on a brand-new account', () => {
  let service: CareerProfileService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(CareerProfileService);
    http = TestBed.inject(HttpTestingController);

    TestBed.inject(AuthService).login('new@cvpal.test', 'a-long-enough-password').subscribe();
    http
      .expectOne((request) => request.url.endsWith('/auth/login'))
      .flush({ access_token: 'access-1', refresh_token: 'refresh-1', token_type: 'bearer' });

    TestBed.tick();
    for (const request of http.match((r) => r.url.endsWith('/users/me'))) {
      request.flush({
        id: 2,
        email: 'new@cvpal.test',
        full_name: null,
        is_active: true,
        created_at: '2026-07-27T10:00:00Z',
      });
    }

    service.profile();
    TestBed.tick();
    http
      .expectOne((request) => request.url.endsWith('/profile'))
      .flush({
        id: 1,
        headline: null,
        summary: null,
        location: null,
        website_url: null,
        github_url: null,
        linkedin_url: null,
        experiences: [],
        educations: [],
        skills: [],
      });
    TestBed.tick();
  });

  afterEach(() => http.verify());

  it('scores an empty profile at 0%, not a free pass on the evidence check', () => {
    // Regression: the evidence check cannot fail with no skills, so counting it in the
    // denominator scored a profile with nothing in it at 17% on first login.
    expect(service.gaps().length).toBe(5);
    expect(service.completeness()).toBe(0);
  });

  it('reports a loaded, untouched profile as empty', () => {
    // Drives the first-run redirect in LayoutComponent. It reads `id > 0` alongside
    // this, so a profile that has not answered yet cannot be mistaken for an empty one.
    expect(service.profile().id).toBeGreaterThan(0);
    expect(service.isEmpty()).toBe(true);
  });
});
