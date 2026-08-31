import { apiFetch, buildBffHeaders, parseApiError } from "@/lib/api-client";
import { parseSseStream } from "@/lib/sse";
import type { ChatProvider } from "@/lib/types";

export type ChatRole = "user" | "assistant" | "tool";

export type RepoSuggestion = {
  name: string;
  full_name: string;
  url: string;
  description: string;
  stars: number;
  language: string | null;
  pushed_at: string | null;
  archived: boolean;
};

/** Mirrors backend/app/schemas/chat.py's ChatMessageOut. */
export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  tool_calls: { id: string; name: string; args: Record<string, unknown> }[] | null;
  tool_call_id: string | null;
  tool_name: string | null;
  tool_result: { repos?: RepoSuggestion[]; error?: string } | Record<string, unknown> | null;
  created_at: string;
};

export type ChatSession = { id: string; title: string; last_message_at: string; starred: boolean };

export type ChatSessionListResponse = { items: ChatSession[]; total: number };

export async function listChatSessions(
  params: {
    q?: string;
    starredOnly?: boolean;
    sort?: "asc" | "desc";
    page?: number;
    pageSize?: number;
  } = {},
): Promise<ChatSessionListResponse> {
  const qs = new URLSearchParams();
  if (params.q) qs.set("q", params.q);
  if (params.starredOnly) qs.set("starred_only", "true");
  if (params.sort) qs.set("sort", params.sort);
  qs.set("page", String(params.page ?? 1));
  qs.set("page_size", String(params.pageSize ?? 20));
  return apiFetch<ChatSessionListResponse>(`chat/sessions?${qs.toString()}`);
}

export async function setSessionStarred(sessionId: string, starred: boolean): Promise<ChatSession> {
  return apiFetch<ChatSession>(`chat/sessions/${sessionId}/star`, {
    method: "PATCH",
    body: JSON.stringify({ starred }),
  });
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  return apiFetch<void>(`chat/sessions/${sessionId}`, { method: "DELETE" });
}

export async function activateChatSession(sessionId: string): Promise<ChatSession> {
  return apiFetch<ChatSession>(`chat/sessions/${sessionId}/activate`, { method: "POST" });
}

export async function createNewChatSession(signal?: AbortSignal): Promise<ChatSession> {
  const headers = buildBffHeaders("POST", {});
  const res = await fetch("/api/bff/chat/sessions/new", {
    method: "POST",
    headers,
    credentials: "same-origin",
    signal,
  });
  if (!res.ok) throw await parseApiError(res);
  return res.json();
}

export async function getOrCreateCurrentSession(signal?: AbortSignal): Promise<ChatSession> {
  const headers = buildBffHeaders("POST", {});
  const res = await fetch("/api/bff/chat/sessions", {
    method: "POST",
    headers,
    credentials: "same-origin",
    signal,
  });
  if (!res.ok) throw await parseApiError(res);
  return res.json();
}

export async function getSessionMessages(sessionId: string, signal?: AbortSignal): Promise<ChatMessage[]> {
  const headers = buildBffHeaders("GET", {});
  const res = await fetch(`/api/bff/chat/sessions/${sessionId}/messages`, {
    headers,
    credentials: "same-origin",
    signal,
  });
  if (!res.ok) throw await parseApiError(res);
  return res.json();
}

// The canonical SSE contract from POST /chat/sessions/{id}/messages — see
// backend/app/routers/chat.py.
export type ChatStreamEvent =
  | { type: "session_meta"; session_id: string; user_message_id: string }
  | { type: "token"; delta: string }
  | { type: "tool_start"; tool_call_id: string; name: string; label: string }
  | { type: "tool_end"; tool_call_id: string; name: string; result: ChatMessage["tool_result"] }
  | { type: "done"; message_id: string | null }
  | { type: "error"; code: string; message: string };

export async function* streamChatTurn(args: {
  sessionId: string;
  content: string;
  provider?: ChatProvider;
  signal?: AbortSignal;
}): AsyncGenerator<ChatStreamEvent> {
  const init: RequestInit = { method: "POST", body: JSON.stringify({ content: args.content, provider: args.provider }) };
  const headers = buildBffHeaders("POST", init);
  const res = await fetch(`/api/bff/chat/sessions/${args.sessionId}/messages`, {
    ...init,
    headers,
    credentials: "same-origin",
    signal: args.signal,
  });
  if (!res.ok || !res.body) throw await parseApiError(res);

  for await (const frame of parseSseStream(res.body)) {
    let payload: Record<string, unknown> = {};
    try {
      payload = frame.data ? JSON.parse(frame.data) : {};
    } catch {
      continue; // malformed frame — ignore rather than crash the stream
    }

    switch (frame.event) {
      case "session_meta":
        yield {
          type: "session_meta",
          session_id: String(payload.session_id ?? ""),
          user_message_id: String(payload.user_message_id ?? ""),
        };
        break;
      case "token":
        yield { type: "token", delta: String(payload.delta ?? "") };
        break;
      case "tool_start":
        yield {
          type: "tool_start",
          tool_call_id: String(payload.tool_call_id ?? ""),
          name: String(payload.name ?? ""),
          label: String(payload.label ?? "Working…"),
        };
        break;
      case "tool_end":
        yield {
          type: "tool_end",
          tool_call_id: String(payload.tool_call_id ?? ""),
          name: String(payload.name ?? ""),
          result: (payload.result as ChatMessage["tool_result"]) ?? null,
        };
        break;
      case "done":
        yield { type: "done", message_id: (payload.message_id as string | null) ?? null };
        break;
      case "error":
        yield { type: "error", code: String(payload.code ?? "UNKNOWN"), message: String(payload.message ?? "Something went wrong") };
        break;
      default:
        break; // unknown event name — ignore rather than crash the stream
    }
  }
}
