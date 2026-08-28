import "server-only";

import { cookies } from "next/headers";
import { COOKIE, FASTAPI_URL } from "./env";

/** Authenticated server-side fetch straight to FastAPI, for use inside Server Components
 * (which don't go through the /api/bff proxy — that's for the browser). Simpler than the
 * full RSC-prefetch + <HydrationBoundary> pattern sketched in DESIGN.md §2; fine for the
 * read-heavy pages here, worth revisiting once the client-side mutation flows (M4+) need
 * TanStack Query cache interop. */
export async function serverApiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const jar = await cookies();
  const accessToken = jar.get(COOKIE.accessToken)?.value;

  const res = await fetch(`${FASTAPI_URL}/api/v1/${path.replace(/^\//, "")}`, {
    ...init,
    headers: { ...init.headers, Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json();
}
