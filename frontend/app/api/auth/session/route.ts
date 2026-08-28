import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { COOKIE, FASTAPI_URL } from "@/lib/env";

export async function GET() {
  const jar = await cookies();
  const accessToken = jar.get(COOKIE.accessToken)?.value;
  if (!accessToken) {
    return NextResponse.json({ user: null }, { status: 401 });
  }

  const upstream = await fetch(`${FASTAPI_URL}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });

  if (!upstream.ok) {
    return NextResponse.json({ user: null }, { status: 401 });
  }

  return NextResponse.json({ user: await upstream.json() });
}
