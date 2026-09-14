/** Turns a bare backend API path (e.g. "projects/{id}/thumbnail") into a URL the browser
 * can actually load in an `<img>`/`<video src>`.
 *
 * This exists because of a real, pre-existing bug: `PhotoUploadResponse.photo_url`
 * (backend/app/schemas/profile.py) is returned as "/api/v1/profile/photo" and handed
 * straight to `<img src>` (components/profile/photo-upload.tsx). Nothing rewrites
 * `/api/v1/*` on the Next side — next.config.ts has no rewrites, and proxy.ts's matcher
 * explicitly excludes `/api` — and the backend requires a Bearer token that a bare
 * `<img>` request never sends. The browser's request 404s/401s and the photo silently
 * never renders.
 *
 * The fix, adopted for every new media URL in this app (project thumbnails/videos, chat
 * attachment previews): the backend returns a bare path with no `/api/v1` prefix, and
 * every consumer builds the actual URL through this function, which always resolves
 * through the authenticated BFF proxy (app/api/bff/[...path]/route.ts) the same way
 * lib/api-client.ts's apiFetch() does. */
export function mediaUrl(path: string): string {
  return `/api/bff/${path.replace(/^\/+/, "")}`;
}
