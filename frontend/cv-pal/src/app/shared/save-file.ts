import { HttpResponse } from '@angular/common/http';

/** Save a blob under a filename. An anchor is the only way a browser offers. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  // Without this the blob is held for the lifetime of the document.
  URL.revokeObjectURL(url);
}

/**
 * The filename the server chose, from `Content-Disposition`.
 *
 * Never rebuilt here: the server sanitises the company and title before putting them in
 * that header, and two places composing a name is two places to disagree about it.
 */
export function filenameOf(response: HttpResponse<Blob>, fallback: string): string {
  const header = response.headers.get('content-disposition') ?? '';
  return /filename="([^"]+)"/.exec(header)?.[1] ?? fallback;
}
