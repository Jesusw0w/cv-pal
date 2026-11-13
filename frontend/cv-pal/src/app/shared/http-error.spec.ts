import { HttpErrorResponse } from '@angular/common/http';

import { detailOf } from './http-error';

const asError = (body: unknown, status = 400) => new HttpErrorResponse({ error: body, status });

describe('detailOf', () => {
  it('returns a flat detail string as it is', () => {
    expect(detailOf(asError({ detail: 'Incorrect email or password' }, 401), 'fallback')).toBe(
      'Incorrect email or password',
    );
  });

  it('reads the messages out of a validation error, without the Pydantic prefix', () => {
    const body = {
      detail: [
        { msg: 'Value error, Password is too common.' },
        { msg: 'Value error, Password must not contain your email.' },
      ],
    };
    expect(detailOf(asError(body, 422), 'fallback')).toBe(
      'Password is too common. Password must not contain your email.',
    );
  });

  it('falls back when the response carries no usable message', () => {
    expect(detailOf(asError({ oops: true }), 'fallback')).toBe('fallback');
    expect(detailOf(asError({ detail: [{ noMessage: true }] }, 422), 'fallback')).toBe('fallback');
    expect(detailOf(new Error('network down'), 'fallback')).toBe('fallback');
  });
});
