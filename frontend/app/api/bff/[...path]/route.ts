import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";
import { COOKIE, FASTAPI_URL } from "@/lib/env";
import { setAuthCookies } from "@/lib/auth-cookies";
import { refreshTokens } from "@/lib/refresh";

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

async function forward(request: NextRequest, accessToken: string, path: string): Promise<Response> {
  const url = `${FASTAPI_URL}/api/v1/${path}${request.nextUrl.search}`;
  const headers = new Headers(request.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);
  headers.delete("host");
  headers.delete("cookie");

  return fetch(url, {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
    // @ts-expect-error - required by undici when streaming a request body
    duplex: "half",
  });
}

async function handle(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path: pathSegments } = await params;
  const path = pathSegments.join("/");
  const jar = await cookies();

  if (MUTATING.has(request.method)) {
    const csrfCookie = jar.get(COOKIE.csrf)?.value;
    const csrfHeader = request.headers.get("x-csrf-token");
    if (!csrfCookie || csrfCookie !== csrfHeader) {
      return NextResponse.json({ code: "CSRF_MISMATCH" }, { status: 403 });
    }
  }

  const accessToken = jar.get(COOKIE.accessToken)?.value;
  if (!accessToken) {
    return NextResponse.json({ code: "SESSION_EXPIRED" }, { status: 401 });
  }

  let upstream = await forward(request, accessToken, path);

  if (upstream.status === 401) {
    const refreshToken = jar.get(COOKIE.refreshToken)?.value;
    const tokens = refreshToken ? await refreshTokens(refreshToken) : null;
    if (!tokens) {
      return NextResponse.json({ code: "SESSION_EXPIRED" }, { status: 401 });
    }
    upstream = await forward(request, tokens.access_token, path);
    const res = new NextResponse(upstream.body, { status: upstream.status, headers: upstream.headers });
    setAuthCookies(res, tokens);
    return res;
  }

  return new NextResponse(upstream.body, { status: upstream.status, headers: upstream.headers });
}

export {
  handle as GET,
  handle as POST,
  handle as PUT,
  handle as PATCH,
  handle as DELETE,
};
