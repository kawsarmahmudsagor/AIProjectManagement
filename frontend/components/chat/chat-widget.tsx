"use client";

import { useState } from "react";
import { ChatPanel } from "@/components/chat/chat-panel";
import { ChatTriggerButton } from "@/components/chat/chat-trigger-button";
import { useChatMessages, useChatSession, useInvalidateChatMessages } from "@/hooks/use-chat-session";
import { useChatStream } from "@/hooks/use-chat-stream";
import type { ChatMessage } from "@/lib/chat";

/** Mounted once in AppShell (auth-only pages) as a fixed bottom-right widget. Owns
 * whether the panel is open; the session/history queries below only start firing once
 * `isOpen` goes true for the first time — matching "the moment the chat window is
 * opened," not page load — and stay cached (staleTime: Infinity) afterward, so closing
 * and reopening the panel is instant and never re-triggers session creation. */
export function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);

  const sessionQuery = useChatSession(isOpen);
  const sessionId = sessionQuery.data?.id;
  const messagesQuery = useChatMessages(sessionId);
  const invalidateMessages = useInvalidateChatMessages();

  const { draft, send } = useChatStream({
    sessionId: sessionId ?? null,
    onUserMessage: (content) => setPendingUserMessage(content),
    onFinalize: () => {
      if (!sessionId) return;
      // Refetch the authoritative persisted history rather than reconstructing it
      // client-side (see hooks/use-chat-stream.ts) — only drop the optimistic bubble
      // once that fresh data has actually landed, so it never flickers away early.
      void invalidateMessages(sessionId).then(() => setPendingUserMessage(null));
    },
  });

  const messages: ChatMessage[] = messagesQuery.data ?? [];
  const displayMessages =
    pendingUserMessage !== null
      ? [
          ...messages,
          {
            id: "__pending__",
            role: "user" as const,
            content: pendingUserMessage,
            tool_calls: null,
            tool_call_id: null,
            tool_name: null,
            tool_result: null,
            created_at: new Date().toISOString(),
          },
        ]
      : messages;

  return (
    <div className="fixed bottom-6 right-6 z-40">
      <div className="relative">
        {isOpen && (
          <ChatPanel
            messages={displayMessages}
            draft={draft}
            loading={sessionQuery.isLoading || messagesQuery.isLoading}
            onSend={(content) => void send(content)}
            onClose={() => setIsOpen(false)}
          />
        )}
        <ChatTriggerButton
          open={isOpen}
          streaming={draft.status === "streaming"}
          onClick={() => setIsOpen((v) => !v)}
        />
      </div>
    </div>
  );
}
