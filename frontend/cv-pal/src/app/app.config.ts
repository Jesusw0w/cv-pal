import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter } from '@angular/router';

import { mockInterceptors } from '../mocks';
import { authInterceptor } from './core/auth';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    // Mock first, so no token is attached to a request that never leaves the browser.
    // In every other build the array is empty and `authInterceptor` is the whole chain.
    provideHttpClient(withInterceptors([...mockInterceptors(), authInterceptor])),
  ],
};
