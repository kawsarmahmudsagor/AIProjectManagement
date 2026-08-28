import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { COOKIE, FASTAPI_URL } from "./env";

export type User = {
  id: string;
  email: string;
  agent_persona: "business_analyst" | "technical_developer";
  first_name: string;
  middle_name: string | null;
  last_name: string | null;
  preferred_name: string | null;
  chat_provider: "gemini" | "ollama";
  chatbot_preemptive_github_suggestions: boolean;
};

/** Real authorization — proxy.ts only does a coarse cookie-presence check (DESIGN.md §5);
 * this is what actually verifies the token against FastAPI. Call from every (app) layout. */
export async function requireSession(): Promise<User> {
  const jar = await cookies();
  const accessToken = jar.get(COOKIE.accessToken)?.value;
  if (!accessToken) redirect("/login");

  const res = await fetch(`${FASTAPI_URL}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });

  if (!res.ok) redirect("/login");
  return res.json();
}
