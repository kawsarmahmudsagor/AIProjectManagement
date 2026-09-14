import { apiFetch } from "@/lib/api-client";
import type { SearchAnswer, SearchHit, SearchResponse } from "@/lib/types";

export async function searchApp(q: string, signal?: AbortSignal): Promise<SearchResponse> {
  const params = new URLSearchParams({ q });
  return apiFetch<SearchResponse>(`search?${params.toString()}`, { signal });
}

export async function askApp(question: string, signal?: AbortSignal): Promise<SearchAnswer> {
  return apiFetch<SearchAnswer>("search/ask", {
    method: "POST",
    body: JSON.stringify({ q: question }),
    signal,
  });
}

/** Routes are already a backend concern for app_feature hits (the registry stores the
 * path) and every other kind's `href` is likewise built server-side — this is just a
 * thin passthrough kept as its own function so call sites don't reach into `hit.href`
 * directly, in case that ever needs to change per-kind on the client. */
export function hrefForHit(hit: SearchHit): string {
  return hit.href;
}
