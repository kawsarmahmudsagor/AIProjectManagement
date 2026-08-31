"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ChatPanel } from "@/components/chat/chat-panel";
import { ChatTriggerButton } from "@/components/chat/chat-trigger-button";
import { useChatWidget } from "@/components/chat/chat-widget-context";
import { useChatMessages, useChatSession, useInvalidateChatMessages } from "@/hooks/use-chat-session";
import { useChatStream } from "@/hooks/use-chat-stream";
import { createNewChatSession, type ChatMessage } from "@/lib/chat";

/** Mounted once in AppShell (auth-only pages) as a fixed bottom-right widget. Open/closed
 * state lives in ChatWidgetProvider (see chat-widget-context.tsx) so other pages — e.g.
 * the Conversations page's "resume" action — can pop it open; the session/history
 * queries below only start firing once `isOpen` goes true for the first time — matching
 * "the moment the chat window is opened," not page load — and stay cached
 * (staleTime: Infinity) afterward, so closing and reopening the panel is instant and
 * never re-triggers session creation. */
export function ChatWidget() {
  const { isOpen, close, toggle } = useChatWidget();
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);
  const [isStartingNew, setIsStartingNew] = useState(false);
  const queryClient = useQueryClient();

  const sessionQuery = useChatSession(isOpen);
  const sessionId = sessionQuery.data?.id;
  const messagesQuery = useChatMessages(sessionId);
  const invalidateMessages = useInvalidateChatMessages();

  async function handleNewChat() {
    setIsStartingNew(true);
    try {
      const session = await createNewChatSession();
      // Setting the cache directly (rather than invalidating) avoids a redundant
      // refetch — we already have the freshly created session from the response, and
      // messagesQuery re-keys to it automatically since it's keyed by sessionId.
      queryClient.setQueryData(["chat", "session"], session);
    } finally {
      setIsStartingNew(false);
    }
  }

  // The "current" session can now change while the widget is mounted/open (the
  // Conversations page's resume flow bumps a different session to "current" and
  // invalidates this query) — drop any optimistic bubble left over from whichever
  // session was showing before, so it can't linger against the newly-resumed one.
  // Render-phase state adjustment (react.dev/learn/you-might-not-need-an-effect),
  // matching ConfirmPopover's prevOpen pattern, rather than an effect.
  const [prevSessionId, setPrevSessionId] = useState(sessionId);
  if (prevSessionId !== sessionId) {
    setPrevSessionId(sessionId);
    setPendingUserMessage(null);
  }

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
            loading={sessionQuery.isLoading || sessionQuery.isFetching || messagesQuery.isLoading}
            onSend={(content) => void send(content)}
            onClose={close}
            onNewChat={() => void handleNewChat()}
            isStartingNew={isStartingNew}
          />
        )}
        <ChatTriggerButton open={isOpen} streaming={draft.status === "streaming"} onClick={toggle} />
      </div>
    </div>
  );
}
