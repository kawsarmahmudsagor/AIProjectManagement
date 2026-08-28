// Next.js 16 renamed `middleware.ts` to `proxy.ts` (DESIGN.md §5). This only does a
// coarse cookie-presence check + redirect — real enforcement is `requireSession()` in
// app/(app)/layout.tsx and the CSRF/token checks in app/api/bff/[...path]/route.ts.
import { NextResponse, type NextRequest } from "next/server";
import { COOKIE } from "@/lib/env";

// Auth pages: unreachable once logged in (bounced to /dashboard instead).
const GUEST_ONLY_PREFIXES = ["/login", "/register", "/forgot-password"];
// Dev-only tooling: reachable regardless of auth state, never redirected either way.
const ALWAYS_PUBLIC_PREFIXES = ["/styleguide"];

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get(COOKIE.accessToken) || request.cookies.get(COOKIE.refreshToken));
  const isGuestOnly = GUEST_ONLY_PREFIXES.some((p) => pathname.startsWith(p));
  const isAlwaysPublic = ALWAYS_PUBLIC_PREFIXES.some((p) => pathname.startsWith(p));

  if (!hasSession && !isGuestOnly && !isAlwaysPublic) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }

  if (hasSession && isGuestOnly) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:png|svg|ico|woff2?)$).*)"],
};
