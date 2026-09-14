"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ChatDock } from "@/components/chat/chat-dock";
import { ChatPanel } from "@/components/chat/chat-panel";
import { ChatTriggerButton } from "@/components/chat/chat-trigger-button";
import { useChatWidget } from "@/components/chat/chat-widget-context";
import { useChatAttachments } from "@/hooks/use-chat-attachments";
import { useChatMessages, useChatSession, useInvalidateChatMessages } from "@/hooks/use-chat-session";
import { useChatStream } from "@/hooks/use-chat-stream";
import { createNewChatSession, type ChatMessage } from "@/lib/chat";
import type { ChatAttachment as ChatAttachmentRef } from "@/lib/types";

/** Mounted once in AppShell (auth-only pages) as a docked/overlay/fullscreen panel (see
 * ChatWidgetContext's `presentation`) — no longer a fixed bottom-right popover. Open/
 * closed state lives in ChatWidgetProvider so other pages — e.g. the Conversations
 * page's "resume" action — can pop it open; the session/history queries below only
 * start firing once `isOpen` goes true for the first time and stay cached
 * (staleTime: Infinity) afterward, so closing and reopening the panel is instant and
 * never re-triggers session creation. */
export function ChatWidget() {
  const { isOpen, close, toggle, draftText, setDraftText } = useChatWidget();
  const [pendingUserTurn, setPendingUserTurn] = useState<{ content: string; attachments: ChatAttachmentRef[] } | null>(
    null,
  );
  const [isStartingNew, setIsStartingNew] = useState(false);
  const queryClient = useQueryClient();

  const sessionQuery = useChatSession(isOpen);
  const sessionId = sessionQuery.data?.id ?? null;
  const messagesQuery = useChatMessages(sessionId ?? undefined);
  const invalidateMessages = useInvalidateChatMessages();
  const attachmentDraft = useChatAttachments(sessionId);

  async function handleNewChat() {
    setIsStartingNew(true);
    try {
      const session = await createNewChatSession();
      // Setting the cache directly (rather than invalidating) avoids a redundant
      // refetch — we already have the freshly created session from the response, and
      // messagesQuery re-keys to it automatically since it's keyed by sessionId.
      queryClient.setQueryData(["chat", "session"], session);
      attachmentDraft.clear();
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
    setPendingUserTurn(null);
  }

  const { draft, send, stop } = useChatStream({
    sessionId,
    onUserMessage: (content, attachmentIds) => {
      const sentAttachments = attachmentDraft.items
        .filter((a) => a.status === "ready" && attachmentIds.includes(a.remote.id))
        .map((a) => (a.status === "ready" ? a.remote : null))
        .filter((a): a is ChatAttachmentRef => a !== null);
      setPendingUserTurn({ content, attachments: sentAttachments });
      attachmentDraft.clear();
    },
    onFinalize: () => {
      if (!sessionId) return;
      // Refetch the authoritative persisted history rather than reconstructing it
      // client-side (see hooks/use-chat-stream.ts) — only drop the optimistic bubble
      // once that fresh data has actually landed, so it never flickers away early.
      void invalidateMessages(sessionId).then(() => setPendingUserTurn(null));
    },
  });

  const messages: ChatMessage[] = messagesQuery.data ?? [];
  const displayMessages: ChatMessage[] =
    pendingUserTurn !== null
      ? [
          ...messages,
          {
            id: "__pending__",
            role: "user" as const,
            content: pendingUserTurn.content,
            tool_calls: null,
            tool_call_id: null,
            tool_name: null,
            tool_result: null,
            created_at: new Date().toISOString(),
            attachments: pendingUserTurn.attachments,
          },
        ]
      : messages;

  return (
    <>
      <ChatDock>
        <ChatPanel
          messages={displayMessages}
          draft={draft}
          composerValue={draftText}
          onComposerChange={setDraftText}
          attachments={attachmentDraft.items}
          onAddFiles={attachmentDraft.add}
          onRemoveAttachment={attachmentDraft.remove}
          onRetryAttachment={attachmentDraft.retry}
          loading={sessionQuery.isLoading || sessionQuery.isFetching || messagesQuery.isLoading}
          onSend={(content, attachmentIds) => void send(content, { attachmentIds })}
          onStop={stop}
          onClose={close}
          onNewChat={() => void handleNewChat()}
          isStartingNew={isStartingNew}
        />
      </ChatDock>
      {/* The FAB only makes sense as a "there's a docked/overlay panel to open" trigger
          — once open, the panel's own header close button is the way out, and a
          floating circle on top of the panel's own content would just be noise. */}
      {!isOpen && (
        <div className="fixed bottom-6 right-6 z-40">
          <ChatTriggerButton streaming={draft.status === "streaming"} onClick={toggle} />
        </div>
      )}
    </>
  );
}
