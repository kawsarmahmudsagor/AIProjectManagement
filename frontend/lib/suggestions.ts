import { apiFetch } from "@/lib/api-client";

/** Mirrors backend/app/schemas/suggestion.py's RepoOut. */
export type SuggestedRepo = {
  name: string;
  full_name: string;
  url: string;
  description: string;
  stars: number;
  language: string | null;
  pushed_at: string | null;
};

/** Mirrors backend/app/schemas/suggestion.py's RepoSuggestionOut — a proactively
 * computed suggestion on the Dashboard's "Suggested for you" card, distinct from the
 * repo cards embedded in a chat message's tool_result (lib/chat.ts's RepoSuggestion). */
export type GithubSuggestion = {
  id: string;
  technology: string;
  repo: SuggestedRepo;
  computed_at: string;
  dismissed: boolean;
};

export async function listGithubSuggestions(): Promise<GithubSuggestion[]> {
  return apiFetch<GithubSuggestion[]>("suggestions/github");
}

export async function dismissGithubSuggestion(id: string): Promise<GithubSuggestion> {
  return apiFetch<GithubSuggestion>(`suggestions/github/${id}/dismiss`, { method: "POST" });
}
