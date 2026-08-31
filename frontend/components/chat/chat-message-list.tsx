"use client";

import { useEffect, useRef } from "react";
import { ChatMessageBubble, hasRepoSuggestions, isRenderable } from "@/components/chat/chat-message-bubble";
import { ToolStatusIndicator } from "@/components/chat/tool-status-indicator";
import type { ChatDraft } from "@/hooks/use-chat-stream";
import type { ChatMessage } from "@/lib/chat";

/** Splits messages into turns (a user message starts a new turn) so repo-suggestion
 * cards can be moved to the end of their own turn instead of rendering in persisted row
 * order — the tool ran (and its row was written) before the model's final reply that
 * references it, so raw order would otherwise show the card above the text. */
function groupByTurn(messages: ChatMessage[]): ChatMessage[][] {
  const turns: ChatMessage[][] = [];
  for (const message of messages) {
    if (message.role === "user" || turns.length === 0) turns.push([message]);
    else turns[turns.length - 1].push(message);
  }
  return turns;
}

function orderedForDisplay(messages: ChatMessage[]): ChatMessage[] {
  return groupByTurn(messages).flatMap((turn) => {
    const cards = turn.filter(hasRepoSuggestions);
    const rest = turn.filter((m) => !hasRepoSuggestions(m));
    return [...rest, ...cards];
  });
}

export function ChatMessageList({ messages, draft }: { messages: ChatMessage[]; draft: ChatDraft }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, draft]);

  return (
    <div className="flex-1 space-y-2 overflow-y-auto px-3 py-3">
      {orderedForDisplay(messages.filter(isRenderable)).map((message) => (
        <ChatMessageBubble key={message.id} message={message} />
      ))}

      {draft.status === "streaming" && (
        <div className="space-y-2">
          {draft.tools.map((tool) => (
            <ToolStatusIndicator key={tool.toolCallId} tool={tool} />
          ))}
          {draft.text && (
            <div className="mr-auto max-w-[85%] rounded-lg rounded-tl-sm border border-border bg-surface px-3 py-2 text-sm">
              {draft.text}
            </div>
          )}
        </div>
      )}

      {draft.status === "error" && (
        <div className="mr-auto max-w-[85%] rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {draft.message}
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
