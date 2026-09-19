import { HttpErrorResponse } from '@angular/common/http';

import { detailOf } from './login.component';

describe('detailOf', () => {
  const asError = (body: unknown, status = 400): HttpErrorResponse =>
    new HttpErrorResponse({ status, error: body });

  it('reads the flat detail string a domain error returns', () => {
    expect(detailOf(asError({ detail: 'Incorrect email or password' }, 401))).toBe(
      'Incorrect email or password',
    );
  });

  it('unwraps the validation list a 422 returns, without its Pydantic prefix', () => {
    // Every password-policy rejection arrives in this shape, so reading `detail`
    // directly puts a stringified array in front of the user.
    const body = {
      detail: [
        { type: 'value_error', loc: ['body'], msg: 'Value error, Password is too common.' },
      ],
    };

    expect(detailOf(asError(body, 422))).toBe('Password is too common.');
  });

  it('gives up rather than guessing when the shape is unrecognised', () => {
    expect(detailOf(asError({ oops: true }))).toBeNull();
    expect(detailOf(asError({ detail: [{ noMessage: true }] }, 422))).toBeNull();
    expect(detailOf(new Error('network down'))).toBeNull();
  });
});
