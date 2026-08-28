"use client";

import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { ChatComposer } from "@/components/chat/chat-composer";
import { ChatMessageList } from "@/components/chat/chat-message-list";
import type { ChatDraft } from "@/hooks/use-chat-stream";
import type { ChatMessage } from "@/lib/chat";
import { cn } from "@/lib/utils";

/** Anchored docked panel, mirroring components/ui/confirm-popover.tsx's mechanics
 * (manual `visible` state + requestAnimationFrame-triggered transition, no portal) —
 * just anchored above its trigger instead of below. */
export function ChatPanel({
  messages,
  draft,
  onSend,
  onClose,
  loading,
}: {
  messages: ChatMessage[];
  draft: ChatDraft;
  onSend: (content: string) => void;
  onClose: () => void;
  loading: boolean;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const raf = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-label="Jarvis chat"
      className={cn(
        "absolute bottom-full right-0 z-30 mb-3 flex h-[560px] w-[380px] origin-bottom-right flex-col overflow-hidden rounded-xl border border-border bg-surface shadow-2xl transition duration-150 ease-out motion-reduce:transition-none",
        visible ? "scale-100 opacity-100" : "pointer-events-none scale-95 opacity-0",
      )}
    >
      <div
        aria-hidden="true"
        className="absolute -bottom-1.5 right-6 h-3 w-3 rotate-45 border-b border-r border-border bg-surface"
      />
      <div className="flex items-center justify-between border-b border-border px-3 py-2.5">
        <span className="text-sm font-semibold">Jarvis</span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close chat"
          className="rounded-lg p-1 text-muted hover:bg-surface-2 hover:text-foreground"
        >
          <X size={16} />
        </button>
      </div>

      {loading ? (
        <div className="flex flex-1 items-center justify-center text-sm text-muted">Loading…</div>
      ) : (
        <ChatMessageList messages={messages} draft={draft} />
      )}

      <ChatComposer disabled={loading || draft.status === "streaming"} onSend={onSend} />
    </div>
  );
}
