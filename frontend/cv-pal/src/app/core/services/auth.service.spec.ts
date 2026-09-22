import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AuthService } from './auth.service';

const COOKIE_SESSION = { access_token: null, refresh_token: null, token_type: 'cookie' };

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);

    service.login('dev@cvpal.test', 'a-long-enough-password').subscribe();
    http.expectOne((request) => request.url.endsWith('/auth/login')).flush(COOKIE_SESSION);
  });

  afterEach(() => http.verify());

  it('is signed in after a cookie login, with nothing in the body to hold', () => {
    expect(service.isAuthenticated()).toBe(true);
  });

  it('spends a refresh token once even when several requests refresh at the same time', () => {
    let settled = 0;
    service.refresh().subscribe(() => settled++);
    service.refresh().subscribe(() => settled++);

    // One call, not two. Refresh tokens are single-use and presenting one twice revokes
    // every session for the user — so a second in-flight refresh would sign them out.
    const refreshes = http.match((request) => request.url.endsWith('/auth/refresh'));
    expect(refreshes.length).toBe(1);
    refreshes[0].flush(COOKIE_SESSION);

    expect(settled).toBe(2);
  });

  it('refreshes again after the previous refresh has settled', () => {
    service.refresh().subscribe();
    http.expectOne((request) => request.url.endsWith('/auth/refresh')).flush(COOKIE_SESSION);

    // The shared observable must be released on completion, or the session can never
    // be refreshed a second time and the user is logged out after 30 minutes.
    service.refresh().subscribe();
    http.expectOne((request) => request.url.endsWith('/auth/refresh')).flush(COOKIE_SESSION);
  });

  it('clears the session locally even if the server is unreachable on logout', () => {
    service.logout();
    http
      .expectOne((request) => request.url.endsWith('/auth/logout'))
      .error(new ProgressEvent('offline'));

    expect(service.isAuthenticated()).toBe(false);
  });
});
