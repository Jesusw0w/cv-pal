import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { CvExtractionResponse } from '../../shared/models/api.model';
import { ImportPanelComponent } from './import-panel.component';

const FOUND: CvExtractionResponse = {
  contact: {
    email: 'ana@example.com',
    phone: '+351 912 345 678',
    linkedin_url: 'linkedin.com/in/ana',
    website_url: null,
  },
  headline: 'Senior Backend Engineer',
  summary: 'Nine years on payment systems.',
  location: 'Lisbon, Portugal',
  experiences: [],
  educations: [],
  skills: [],
};

describe('ImportPanelComponent', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
  });

  it('proposes the header fields a CV carries', () => {
    const panel = TestBed.createComponent(ImportPanelComponent).componentInstance;

    const fields = panel.proposedFields(FOUND).map((field) => field.field);

    expect(fields).toEqual(['headline', 'location', 'phone', 'summary', 'linkedin_url']);
  });

  it('treats a header with nothing readable in it as an empty proposal', () => {
    // Empty is a normal outcome for a scanned CV, and the panel says so rather than
    // rendering a list of blank rows.
    const panel = TestBed.createComponent(ImportPanelComponent).componentInstance;

    const nothing: CvExtractionResponse = {
      ...FOUND,
      contact: { email: null, phone: null, linkedin_url: null, website_url: null },
      headline: null,
      summary: null,
      location: null,
    };

    expect(panel.isEmpty(nothing)).toBe(true);
    expect(panel.isEmpty(FOUND)).toBe(false);
  });

  it('says up front when the read missed dates or names', () => {
    // The per-row warnings are easy to miss on a long list; "Add all" skips those rows.
    const panel = TestBed.createComponent(ImportPanelComponent).componentInstance;
    const role = {
      organisation: 'Globex Corporation',
      title: 'Staff Engineer',
      location: null,
      start_date: '2020-01-01',
      end_date: null,
      description: null,
    };

    const issues = panel.readIssues({
      ...FOUND,
      experiences: [role, { ...role, start_date: null }, { ...role, organisation: '' }],
    });

    expect(issues).toContain('Dates could not be read for 1 of 3 roles');
    expect(issues).toContain('1 entry is missing a name or a title');
    expect(panel.readIssues({ ...FOUND, experiences: [role] })).toBeNull();
  });

  it('refuses to add a role with no employer rather than sending a blank one', () => {
    const panel = TestBed.createComponent(ImportPanelComponent).componentInstance;

    panel.addRole({
      organisation: '',
      title: 'Staff Engineer',
      location: null,
      start_date: '2020-01-01',
      end_date: null,
      description: null,
    });

    expect(panel.error()).toContain('Add that role by hand');
    expect(panel.busy()).toBe(false);
  });
});
