import { HttpInterceptorFn } from '@angular/common/http';

import { environment } from '../environments/environment';
import { mockApiInterceptor } from './mock-api.interceptor';

/**
 * The interceptors to register, given the active environment.
 *
 * Returning an empty array in non-mock builds keeps the mock code out of the request
 * path entirely; bundlers can also drop it, since `environment.useMocks` is a build-time
 * constant.
 */
export function mockInterceptors(): HttpInterceptorFn[] {
  return environment.useMocks ? [mockApiInterceptor] : [];
}

export { mockApiInterceptor, resetMockBackend } from './mock-api.interceptor';
export { MockBackend, MockHttpError } from './mock-backend';
