"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useChatWidget } from "@/components/chat/chat-widget-context";
import { DeleteConversationButton } from "@/components/conversations/delete-conversation-button";
import { StarToggleButton } from "@/components/conversations/star-toggle-button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/lib/api-client";
import { activateChatSession, type ChatSession } from "@/lib/chat";
import { cn } from "@/lib/utils";

function formatTimestamp(iso: string) {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function ConversationList({ sessions }: { sessions: ChatSession[] }) {
  const queryClient = useQueryClient();
  const { open } = useChatWidget();
  const [resumingId, setResumingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleResume(sessionId: string) {
    setResumingId(sessionId);
    setError(null);
    try {
      await activateChatSession(sessionId);
      await queryClient.invalidateQueries({ queryKey: ["chat", "session"] });
      open();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to open conversation.");
    } finally {
      setResumingId(null);
    }
  }

  if (sessions.length === 0) {
    return <p className="text-sm text-muted">No conversations match your filters.</p>;
  }

  return (
    <Card className="divide-y divide-border p-0">
      {error && <p className="px-4 py-2 text-sm text-danger">{error}</p>}
      {sessions.map((session) => (
        <div
          key={session.id}
          role="button"
          tabIndex={0}
          onClick={() => void handleResume(session.id)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              void handleResume(session.id);
            }
          }}
          className={cn(
            "flex cursor-pointer items-center justify-between gap-3 px-4 py-3 hover:bg-surface-2",
            resumingId === session.id && "opacity-60",
          )}
        >
          <div className="min-w-0">
            <p className="truncate font-medium">{session.title}</p>
            <p className="text-xs text-muted">{formatTimestamp(session.last_message_at)}</p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <StarToggleButton sessionId={session.id} starred={session.starred} />
            <DeleteConversationButton sessionId={session.id} sessionTitle={session.title} />
          </div>
        </div>
      ))}
    </Card>
  );
}
