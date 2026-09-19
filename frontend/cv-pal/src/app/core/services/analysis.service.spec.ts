import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AnalysisService, MAX_CV_BYTES, rejectUpload } from './analysis.service';

const fileOf = (name: string, bytes = 10): File =>
  new File([new Uint8Array(bytes)], name, { type: 'application/pdf' });

describe('rejectUpload', () => {
  it('accepts the formats the API accepts', () => {
    expect(rejectUpload(fileOf('cv.pdf'))).toBeNull();
    expect(rejectUpload(fileOf('cv.docx'))).toBeNull();
    expect(rejectUpload(fileOf('CV.PDF'))).toBeNull();
  });

  it('refuses a format the API would reject anyway', () => {
    // Refused here only to answer instantly — the API enforces the same rule.
    expect(rejectUpload(fileOf('cv.txt'))).toContain('.pdf');
    expect(rejectUpload(fileOf('cv'))).toContain('.pdf');
  });

  it('refuses a file over the size limit', () => {
    expect(rejectUpload(fileOf('cv.pdf', MAX_CV_BYTES + 1))).toContain('10 MB');
  });
});

describe('AnalysisService', () => {
  let service: AnalysisService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AnalysisService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('posts an upload to the trailing-slash collection route', () => {
    // Without the trailing slash FastAPI answers with a redirect, and the multipart
    // body does not survive it.
    service.upload(fileOf('cv.pdf')).subscribe();

    const request = http.expectOne((r) => r.url.endsWith('/cvs/'));
    expect(request.request.method).toBe('POST');
    expect(request.request.body instanceof FormData).toBe(true);
    request.flush({ id: 1, user_id: 1, filename: 'cv.pdf', version: 1, created_at: '' });
  });

  it('sends the posting as job_description on the coverage endpoint', () => {
    service.checkCoverage(7, 'Requirements: Python and Docker.').subscribe();

    const request = http.expectOne((r) => r.url.endsWith('/analysis/cvs/7/coverage'));
    expect(request.request.body).toEqual({
      job_description: 'Requirements: Python and Docker.',
    });
    request.flush({ score: 50, matched: [], missing: [], missing_required: [] });
  });

  it('runs the ATS check with no body — it needs only the CV', () => {
    service.checkParseability(7).subscribe();

    const request = http.expectOne((r) => r.url.endsWith('/analysis/cvs/7/ats-check'));
    expect(request.request.method).toBe('POST');
    request.flush({ score: 90, word_count: 500, findings: [], blocking: [] });
  });
});
