"use client";

import { Maximize2, Minimize2, SquarePen, X } from "lucide-react";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { ChatComposer } from "@/components/chat/chat-composer";
import { ChatMessageList } from "@/components/chat/chat-message-list";
import { useChatWidget } from "@/components/chat/chat-widget-context";
import type { DraftAttachment } from "@/hooks/use-chat-attachments";
import { useEnterTransition } from "@/hooks/use-enter-transition";
import type { ChatDraft } from "@/hooks/use-chat-stream";
import type { ChatMessage } from "@/lib/chat";
import { cn } from "@/lib/utils";

/** The conversation panel's content — the docked/overlay/fullscreen chrome around it
 * lives in ChatDock; this component only renders what's inside that chrome, so it fills
 * whatever box it's given (`flex h-full w-full flex-col`) rather than sizing itself. */
export function ChatPanel({
  messages,
  draft,
  composerValue,
  onComposerChange,
  attachments,
  onAddFiles,
  onRemoveAttachment,
  onRetryAttachment,
  onSend,
  onStop,
  onClose,
  onNewChat,
  isStartingNew,
  loading,
}: {
  messages: ChatMessage[];
  draft: ChatDraft;
  composerValue: string;
  onComposerChange: (value: string) => void;
  attachments: DraftAttachment[];
  onAddFiles: (files: File[]) => void;
  onRemoveAttachment: (localId: string) => void;
  onRetryAttachment: (localId: string) => void;
  onSend: (content: string, attachmentIds: string[]) => void;
  onStop: () => void;
  onClose: () => void;
  onNewChat: () => void;
  isStartingNew: boolean;
  loading: boolean;
}) {
  const { presentation, isFullScreen, toggleFullScreen } = useChatWidget();
  const visible = useEnterTransition();
  const [dragActive, setDragActive] = useState(false);
  // A depth counter, not a boolean: unlike the standalone document-upload dropzone, this
  // panel is full of child elements, so dragenter/dragleave fire constantly as the
  // pointer crosses them — only treat the drag as "left" once depth returns to 0. A
  // plain ref (not a plain object literal) so the count survives across renders, not
  // just within one.
  const dragDepth = useRef(0);

  // Escape closes an overlay/fullscreen presentation (a real dialog-ish surface); a
  // docked column is a persistent part of the page, not a dialog, so Escape does
  // nothing there — matching a sidebar, not a modal.
  useEffect(() => {
    if (presentation === "docked") return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [presentation, onClose]);

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(false);
    const files = Array.from(e.dataTransfer.files ?? []);
    if (files.length) onAddFiles(files);
  };

  return (
    <div
      role="dialog"
      aria-modal={presentation === "docked" ? "false" : "true"}
      aria-label="Jarvis chat"
      onDragOver={(e) => {
        e.preventDefault();
        setDragActive(true);
      }}
      onDragEnter={() => {
        dragDepth.current += 1;
      }}
      onDragLeave={() => {
        dragDepth.current -= 1;
        if (dragDepth.current <= 0) setDragActive(false);
      }}
      onDrop={onDrop}
      className={cn(
        "relative flex h-full min-h-0 w-full flex-col overflow-hidden transition duration-150 ease-out motion-reduce:transition-none",
        visible ? "translate-x-0 opacity-100" : "pointer-events-none translate-x-2 opacity-0",
      )}
    >
      {dragActive && (
        <div className="pointer-events-none absolute inset-2 z-20 flex items-center justify-center rounded-lg border-2 border-dashed border-accent bg-accent/5 text-sm font-medium text-accent">
          Drop to attach
        </div>
      )}
      <div className="flex items-center justify-between border-b border-border px-3 py-2.5">
        <span className="text-sm font-semibold">Jarvis</span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onNewChat}
            disabled={isStartingNew || loading}
            aria-label="New conversation"
            title="New conversation"
            className="rounded-lg p-1 text-muted hover:bg-surface-2 hover:text-foreground disabled:opacity-50"
          >
            <SquarePen size={16} />
          </button>
          <button
            type="button"
            onClick={toggleFullScreen}
            aria-label={isFullScreen ? "Exit full screen" : "Full screen"}
            title={isFullScreen ? "Exit full screen" : "Full screen"}
            className="rounded-lg p-1 text-muted hover:bg-surface-2 hover:text-foreground"
          >
            {isFullScreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </button>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close chat"
            className="rounded-lg p-1 text-muted hover:bg-surface-2 hover:text-foreground"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-1 items-center justify-center text-sm text-muted">Loading…</div>
      ) : (
        <ChatMessageList messages={messages} draft={draft} />
      )}

      <ChatComposer
        disabled={loading}
        streaming={draft.status === "streaming"}
        value={composerValue}
        onChange={onComposerChange}
        attachments={attachments}
        onAddFiles={onAddFiles}
        onRemoveAttachment={onRemoveAttachment}
        onRetryAttachment={onRetryAttachment}
        onSend={onSend}
        onStop={onStop}
        hasPendingUploads={attachments.some((a) => a.status === "uploading")}
      />
    </div>
  );
}
