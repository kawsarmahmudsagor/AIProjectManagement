import { NextResponse } from "next/server";
import { FASTAPI_URL } from "@/lib/env";
import { setAuthCookies } from "@/lib/auth-cookies";

export async function POST(request: Request) {
  const body = await request.json();

  const upstream = await fetch(`${FASTAPI_URL}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!upstream.ok) {
    const detail = await upstream.json().catch(() => ({ detail: "Registration failed" }));
    return NextResponse.json(detail, { status: upstream.status });
  }

  const data = await upstream.json();
  const res = NextResponse.json({ user: data.user }, { status: 201 });
  setAuthCookies(res, data);
  return res;
}
