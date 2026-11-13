import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  TitleStrategy,
  provideRouter,
  withComponentInputBinding,
  withInMemoryScrolling,
} from '@angular/router';

import { mockInterceptors } from '../mocks';
import { authInterceptor } from './core/auth';
import { PageTitleStrategy } from './core/page-title';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(
      routes,
      // Route data reaches components as inputs: how a section is handed its tabs.
      withComponentInputBinding(),
      withInMemoryScrolling({ scrollPositionRestoration: 'enabled' }),
    ),
    { provide: TitleStrategy, useExisting: PageTitleStrategy },
    // Mock first, so no token is attached to a request that never leaves the browser.
    // In every other build the array is empty and `authInterceptor` is the whole chain.
    provideHttpClient(withInterceptors([...mockInterceptors(), authInterceptor])),
  ],
};
