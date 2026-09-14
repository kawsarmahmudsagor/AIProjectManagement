"use client";

import { Send, Square } from "lucide-react";
import { useRef, type ClipboardEvent, type KeyboardEvent } from "react";
import { ChatAttachMenu } from "@/components/chat/chat-attach-menu";
import { ChatAttachmentChip } from "@/components/chat/chat-attachment-chip";
import { Button } from "@/components/ui/button";
import type { DraftAttachment } from "@/hooks/use-chat-attachments";

const MAX_COMPOSER_PX = 160; // ~6 lines — a docked full-height panel can afford more than the old 96px cap

export function ChatComposer({
  disabled,
  streaming,
  value,
  onChange,
  attachments,
  onAddFiles,
  onRemoveAttachment,
  onRetryAttachment,
  onSend,
  onStop,
  hasPendingUploads,
}: {
  disabled: boolean;
  streaming: boolean;
  value: string;
  onChange: (value: string) => void;
  attachments: DraftAttachment[];
  onAddFiles: (files: File[]) => void;
  onRemoveAttachment: (localId: string) => void;
  onRetryAttachment: (localId: string) => void;
  onSend: (content: string, attachmentIds: string[]) => void;
  onStop: () => void;
  hasPendingUploads: boolean;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const readyIds = attachments.filter((a) => a.status === "ready").map((a) => a.remote.id);
  const canSend = !disabled && !hasPendingUploads && (value.trim().length > 0 || readyIds.length > 0);

  const submit = () => {
    if (!canSend) return;
    onSend(value.trim(), readyIds);
    onChange("");
    const el = textareaRef.current;
    if (el) el.style.height = "auto";
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const onPaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = Array.from(e.clipboardData.files);
    if (files.length) {
      e.preventDefault();
      onAddFiles(files);
    }
  };

  const autoGrow = (el: HTMLTextAreaElement) => {
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_COMPOSER_PX)}px`;
  };

  return (
    <div className="border-t border-border p-2">
      {attachments.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {attachments.map((a) => (
            <ChatAttachmentChip
              key={a.localId}
              attachment={a}
              onRemove={() => onRemoveAttachment(a.localId)}
              onRetry={() => onRetryAttachment(a.localId)}
            />
          ))}
        </div>
      )}
      <div className="flex items-end gap-2">
        <ChatAttachMenu onFiles={onAddFiles} disabled={disabled} />
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            autoGrow(e.target);
          }}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          disabled={disabled}
          rows={1}
          placeholder="Ask Jarvis about your projects…"
          style={{ maxHeight: MAX_COMPOSER_PX }}
          className="flex-1 resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/50 disabled:opacity-60"
        />
        {streaming ? (
          <Button type="button" onClick={onStop} aria-label="Stop generating" iconOnly>
            <Square size={13} />
          </Button>
        ) : (
          <Button type="button" onClick={submit} disabled={!canSend} aria-label="Send message" iconOnly>
            <Send size={15} />
          </Button>
        )}
      </div>
    </div>
  );
}
