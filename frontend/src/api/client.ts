// Typed fetch wrapper for the CapitalOS backend.
// - credentials: 'include' so the session cookie rides along
// - reads the `capitalos_csrf` cookie and echoes it in X-CSRF-Token on mutations
// - parses {detail, request_id} error envelopes into a typed ApiError
// - supports JSON (default) and multipart uploads

export const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1';

const CSRF_COOKIE = 'capitalos_csrf';
const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export interface ApiErrorBody {
  detail?: string | { msg?: string; loc?: (string | number)[] }[];
  request_id?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly requestId?: string;
  readonly detail: unknown;

  constructor(status: number, message: string, detail: unknown, requestId?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.requestId = requestId;
  }

  get isAuthError(): boolean {
    return this.status === 401;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }
}

function readCookie(name: string): string | null {
  const match = document.cookie.match(
    new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)'),
  );
  return match ? decodeURIComponent(match[1]) : null;
}

function normaliseDetail(body: ApiErrorBody | undefined, fallback: string): string {
  if (!body || body.detail == null) return fallback;
  if (typeof body.detail === 'string') return body.detail;
  if (Array.isArray(body.detail)) {
    const parts = body.detail
      .map((d) => {
        const loc = Array.isArray(d.loc) ? d.loc.filter((p) => p !== 'body').join('.') : '';
        return loc ? `${loc}: ${d.msg ?? ''}`.trim() : d.msg ?? '';
      })
      .filter(Boolean);
    if (parts.length) return parts.join('; ');
  }
  return fallback;
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  /** Query-string params; undefined/null values are dropped. */
  params?: Record<string, string | number | boolean | undefined | null>;
  /** JSON body (serialised automatically). Mutually exclusive with `formData`. */
  json?: unknown;
  /** Multipart body for uploads. Mutually exclusive with `json`. */
  formData?: FormData;
}

function buildUrl(path: string, params?: RequestOptions['params']): string {
  const base = path.startsWith('http') ? path : `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
  if (!params) return base;
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    usp.append(key, String(value));
  }
  const qs = usp.toString();
  return qs ? `${base}?${qs}` : base;
}

async function request<T>(path: string, method: string, opts: RequestOptions = {}): Promise<T> {
  const { params, json, formData, headers, ...rest } = opts;
  const finalHeaders = new Headers(headers);

  let body: BodyInit | undefined;
  if (formData) {
    body = formData; // browser sets multipart boundary
  } else if (json !== undefined) {
    finalHeaders.set('Content-Type', 'application/json');
    body = JSON.stringify(json);
  }

  if (MUTATING_METHODS.has(method.toUpperCase())) {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) finalHeaders.set('X-CSRF-Token', csrf);
  }
  finalHeaders.set('Accept', 'application/json');

  const res = await fetch(buildUrl(path, params), {
    method,
    credentials: 'include',
    headers: finalHeaders,
    body,
    ...rest,
  });

  if (res.status === 204 || res.headers.get('content-length') === '0') {
    if (!res.ok) throw new ApiError(res.status, res.statusText || 'Request failed', undefined);
    return undefined as T;
  }

  const contentType = res.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  const payload = isJson ? await res.json().catch(() => undefined) : await res.text();

  if (!res.ok) {
    const bodyObj = (isJson ? payload : undefined) as ApiErrorBody | undefined;
    const message = normaliseDetail(bodyObj, res.statusText || `HTTP ${res.status}`);
    throw new ApiError(res.status, message, payload, bodyObj?.request_id);
  }

  return payload as T;
}

/** Download a URL as a browser file save (used for CSV/JSON exports & templates). */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const res = await fetch(buildUrl(path), {
    method: 'GET',
    credentials: 'include',
    headers: { Accept: 'application/octet-stream' },
  });
  if (!res.ok) {
    let requestId: string | undefined;
    let message = res.statusText || `HTTP ${res.status}`;
    try {
      const body = (await res.json()) as ApiErrorBody;
      requestId = body.request_id;
      message = normaliseDetail(body, message);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message, undefined, requestId);
  }
  const blob = await res.blob();
  const disposition = res.headers.get('content-disposition') || '';
  const nameMatch = disposition.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i);
  const filename = nameMatch ? decodeURIComponent(nameMatch[1].replace(/"/g, '')) : fallbackName;

  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const api = {
  get: <T>(path: string, opts?: RequestOptions) => request<T>(path, 'GET', opts),
  post: <T>(path: string, opts?: RequestOptions) => request<T>(path, 'POST', opts),
  put: <T>(path: string, opts?: RequestOptions) => request<T>(path, 'PUT', opts),
  patch: <T>(path: string, opts?: RequestOptions) => request<T>(path, 'PATCH', opts),
  delete: <T>(path: string, opts?: RequestOptions) => request<T>(path, 'DELETE', opts),
  download: downloadFile,
};
