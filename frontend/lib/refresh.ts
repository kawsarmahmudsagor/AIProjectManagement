import { FASTAPI_URL } from "./env";
import type { TokenPair } from "./auth-cookies";

/** Single-flight per server instance — a multi-instance deployment would need a shared
 * lock; not needed at this stack's scale (see backend/DESIGN.md §6 on avoiding Redis). */
let inFlight: Promise<TokenPair | null> | null = null;

export async function refreshTokens(refreshToken: string): Promise<TokenPair | null> {
  inFlight ??= (async () => {
    const upstream = await fetch(`${FASTAPI_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    return upstream.ok ? ((await upstream.json()) as TokenPair) : null;
  })().finally(() => {
    inFlight = null;
  });

  return inFlight;
}
