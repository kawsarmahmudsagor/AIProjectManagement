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

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);

  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrf = readCookie(COOKIE.csrf);
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`/api/bff/${path.replace(/^\//, "")}`, {
    ...init,
    method,
    headers,
    credentials: "same-origin",
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ message: res.statusText }));
    // FastAPI wraps a raised HTTPException's `detail` — a plain string for most routes
    // ("Job not found"), or a {code, message, provider} dict for the ones that need a
    // machine-readable code (documents.py, ai.py).
    const detail = body.detail;
    const isStructured = Boolean(detail) && typeof detail === "object";
    throw new ApiError(
      res.status,
      isStructured ? detail.code : undefined,
      (isStructured ? detail.message : detail) ?? body.message ?? res.statusText,
      isStructured ? detail.provider : undefined,
    );
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}
