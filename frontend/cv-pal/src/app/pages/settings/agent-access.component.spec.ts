import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AgentAccessComponent } from './agent-access.component';

const LISTED = {
  id: 1,
  name: 'Claude Desktop',
  display_hint: 'abcdefgh',
  scopes: 'cvpal:read',
  expires_at: '2099-01-01T00:00:00Z',
  last_used_at: null,
  created_at: '2026-09-22T00:00:00Z',
};

describe('AgentAccessComponent', () => {
  let http: HttpTestingController;

  async function render(mcpEnabled: boolean) {
    TestBed.configureTestingModule({
      imports: [AgentAccessComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(AgentAccessComponent);
    fixture.detectChanges();
    http
      .expectOne((request) => request.url.endsWith('/users/me/tokens'))
      .flush({ mcp_enabled: mcpEnabled, tokens: [LISTED] });
    await fixture.whenStable();
    fixture.detectChanges();
    return fixture;
  }

  afterEach(() => http.verify());

  it('says so when the instance does not accept agents, and will not create a token', async () => {
    const fixture = await render(false);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('CV_PAL_MCP_ENABLED=true');
    expect(fixture.componentInstance.canCreate()).toBe(false);
  });

  it('lists tokens by their hint, never their secret', async () => {
    const fixture = await render(true);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('Claude Desktop');
    expect(text).toContain('cvp_abcdefgh…');
    expect(text).toContain('read only');
  });

  it('shows a new secret once, until dismissed', async () => {
    const fixture = await render(true);
    const component = fixture.componentInstance;
    component.name.set('laptop');
    component.password.set('a-long-enough-password');

    component.create();
    http
      .expectOne((request) => request.method === 'POST')
      .flush({ ...LISTED, id: 2, name: 'laptop', token: 'cvp_secret-value' });
    // Creating reloads the list, which the resource sends on its next tick.
    TestBed.tick();
    http
      .expectOne((request) => request.url.endsWith('/users/me/tokens'))
      .flush({ mcp_enabled: true, tokens: [LISTED] });
    await fixture.whenStable();
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('cvp_secret-value');
    expect(component.password()).toBe('');

    component.created.set(null);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('cvp_secret-value');
  });
});
