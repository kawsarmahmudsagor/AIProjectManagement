"use client";

import { COOKIE } from "./env";

/** Minimal typed fetch wrapper against the BFF (app/api/bff/[...path]/route.ts).
 * A real @hey-api/openapi-ts codegen client (DESIGN.md §6) is the next step once the
 * OpenAPI schema stabilizes — this hand-written version keeps the M0/M1 shell functional
 * without depending on the backend being up during frontend-only development. */

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string | undefined,
    message: string,
    public provider: string | undefined = undefined,
  ) {
    super(message);
  }
}

/** Attaches the CSRF header for mutating verbs and a default Content-Type for a JSON
 * body — the bit of `apiFetch` that any other BFF caller (e.g. lib/chat.ts's streaming
 * fetch, which can't just call `apiFetch` since it needs the raw Response body) also
 * needs, so it's factored out rather than duplicated. */
export function buildBffHeaders(method: string, init: RequestInit): Headers {
  const headers = new Headers(init.headers);
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method.toUpperCase())) {
    const csrf = readCookie(COOKIE.csrf);
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

/** Parses a failed BFF response into an ApiError — same FastAPI `detail` shape handling
 * `apiFetch` does below, factored out so lib/chat.ts's streaming fetch (which can't use
 * `apiFetch` itself, see buildBffHeaders) doesn't duplicate this parsing. */
export async function parseApiError(res: Response): Promise<ApiError> {
  const body = await res.json().catch(() => ({ message: res.statusText }));
  const detail = body.detail;
  const isStructured = Boolean(detail) && typeof detail === "object";
  return new ApiError(
    res.status,
    isStructured ? detail.code : undefined,
    (isStructured ? detail.message : detail) ?? body.message ?? res.statusText,
    isStructured ? detail.provider : undefined,
  );
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = buildBffHeaders(method, init);

  const res = await fetch(`/api/bff/${path.replace(/^\//, "")}`, {
    ...init,
    method,
    headers,
    credentials: "same-origin",
  });

  if (!res.ok) throw await parseApiError(res);
  if (res.status === 204) return undefined as T;
  return res.json();
}
