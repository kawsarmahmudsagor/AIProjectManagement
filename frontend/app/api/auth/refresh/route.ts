import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { COOKIE } from "@/lib/env";
import { clearAuthCookies, setAuthCookies } from "@/lib/auth-cookies";
import { refreshTokens } from "@/lib/refresh";

export async function POST() {
  const jar = await cookies();
  const refreshToken = jar.get(COOKIE.refreshToken)?.value;
  if (!refreshToken) {
    return NextResponse.json({ code: "SESSION_EXPIRED" }, { status: 401 });
  }

  const tokens = await refreshTokens(refreshToken);
  if (!tokens) {
    const res = NextResponse.json({ code: "SESSION_EXPIRED" }, { status: 401 });
    clearAuthCookies(res);
    return res;
  }

  const res = NextResponse.json({ ok: true });
  setAuthCookies(res, tokens);
  return res;
}
