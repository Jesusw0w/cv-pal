import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AuthService } from './auth.service';
import {
  LinkedInService,
  needsDataExport,
  rejectLinkedInFile,
} from './linkedin.service';

describe('LinkedInService', () => {
  let service: LinkedInService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(LinkedInService);
    http = TestBed.inject(HttpTestingController);

    TestBed.inject(AuthService).login('dev@cvpal.test', 'a-long-enough-password').subscribe();
    http
      .expectOne((request) => request.url.endsWith('/auth/login'))
      .flush({ access_token: 'access-1', refresh_token: 'refresh-1', token_type: 'bearer' });

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
  });

  it('sends an import as multipart, not JSON', () => {
    // The API takes a file or a form field, so a JSON body would never reach the parser.
    service.paste('a'.repeat(200)).subscribe();

    const request = http.expectOne((r) => r.url.endsWith('/linkedin/import'));
    expect(request.request.method).toBe('POST');
    expect(request.request.body instanceof FormData).toBe(true);
    request.flush({});
  });

  it('says a data export would still add something after a PDF import', () => {
    // The whole point of tracking provenance: a profile PDF carries only the top three
    // skills, so the screen has to be able to tell the user what is still missing.
    expect(needsDataExport({ identity: 'pdf', skills: 'pdf' })).toBe(true);
    expect(needsDataExport({ identity: 'export', skills: 'pdf' })).toBe(true);
    expect(needsDataExport({ identity: 'export', skills: 'export' })).toBe(false);
    // Nothing imported yet is not a reason to nag about the export.
    expect(needsDataExport(undefined)).toBe(false);
  });

  it('accepts a profile PDF and a data-export archive, and nothing else', () => {
    const pdf = new File(['x'], 'Profile.pdf', { type: 'application/pdf' });
    const zip = new File(['x'], 'Basic_LinkedInDataExport.zip', { type: 'application/zip' });
    const docx = new File(['x'], 'profile.docx');

    expect(rejectLinkedInFile(pdf)).toBeNull();
    expect(rejectLinkedInFile(zip)).toBeNull();
    expect(rejectLinkedInFile(docx)).not.toBeNull();
  });
});
