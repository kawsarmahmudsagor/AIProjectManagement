import type { NextResponse } from "next/server";
import { COOKIE } from "./env";

const ACCESS_MAX_AGE = 15 * 60; // must track backend ACCESS_TOKEN_EXPIRE_MINUTES
const REFRESH_MAX_AGE = 30 * 24 * 60 * 60; // must track backend REFRESH_TOKEN_EXPIRE_DAYS

export type TokenPair = { access_token: string; refresh_token: string };

/** Sets httpOnly access/refresh cookies plus a JS-readable CSRF cookie (double-submit —
 * see DESIGN.md §5). The browser never sees a JWT. */
export function setAuthCookies(res: NextResponse, tokens: TokenPair) {
  res.cookies.set(COOKIE.accessToken, tokens.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: ACCESS_MAX_AGE,
  });
  res.cookies.set(COOKIE.refreshToken, tokens.refresh_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/api/auth",
    maxAge: REFRESH_MAX_AGE,
  });
  res.cookies.set(COOKIE.csrf, crypto.randomUUID(), {
    httpOnly: false,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: REFRESH_MAX_AGE,
  });
}

export function clearAuthCookies(res: NextResponse) {
  for (const name of [COOKIE.accessToken, COOKIE.refreshToken, COOKIE.csrf]) {
    res.cookies.set(name, "", { path: "/", maxAge: 0 });
  }
}
