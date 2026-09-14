import { NextResponse, type NextRequest } from "next/server";
import { parseThemeCookie, THEME_COOKIE, THEME_MAX_AGE } from "@/lib/theme";

/** Sets the theme preference cookie so app/layout.tsx can stamp the right `data-theme`
 * server-side on the very next request — no blocking inline script, no flash, no
 * hydration mismatch (see the theme toggle's usage of this route). Not behind CSRF like
 * the BFF proxy's mutating verbs: this cookie carries no secret and controls nothing
 * but which CSS variables apply, so a cross-site POST to it is at most a mild annoyance,
 * not a security issue. */
export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const choice = parseThemeCookie(body?.theme);

  const res = NextResponse.json({ theme: choice });
  if (choice === "system") {
    res.cookies.set(THEME_COOKIE, "", { path: "/", maxAge: 0 });
  } else {
    res.cookies.set(THEME_COOKIE, choice, {
      httpOnly: false,
      sameSite: "lax",
      path: "/",
      maxAge: THEME_MAX_AGE,
    });
  }
  return res;
}
