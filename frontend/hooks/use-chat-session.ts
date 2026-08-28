"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getOrCreateCurrentSession, getSessionMessages } from "@/lib/chat";

/** Lazily fetch-or-creates the user's current chat session only once the widget is
 * actually opened (matching "the moment the chat window is opened", not page load) —
 * `enabled` gates that. Session creation is idempotent server-side (see
 * chat_service.get_or_create_current_session), so calling this repeatedly is harmless. */
export function useChatSession(enabled: boolean) {
  return useQuery({
    queryKey: ["chat", "session"],
    queryFn: () => getOrCreateCurrentSession(),
    enabled,
    staleTime: Infinity,
  });
}

export function useChatMessages(sessionId: string | undefined) {
  return useQuery({
    queryKey: ["chat", "messages", sessionId],
    queryFn: () => getSessionMessages(sessionId as string),
    enabled: Boolean(sessionId),
    staleTime: Infinity,
  });
}

export function useInvalidateChatMessages() {
  const queryClient = useQueryClient();
  return (sessionId: string) => queryClient.invalidateQueries({ queryKey: ["chat", "messages", sessionId] });
}
