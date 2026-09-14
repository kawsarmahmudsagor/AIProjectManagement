import { File, Loader2, RotateCcw, X } from "lucide-react";
import { formatBytes } from "@/lib/chat-attachments";
import type { DraftAttachment } from "@/hooks/use-chat-attachments";
import { cn } from "@/lib/utils";

export function ChatAttachmentChip({
  attachment,
  onRemove,
  onRetry,
}: {
  attachment: DraftAttachment;
  onRemove: () => void;
  onRetry: () => void;
}) {
  const isImage = attachment.file.type.startsWith("image/");

  return (
    <div
      className={cn(
        "relative flex h-10 items-center gap-2 rounded-lg border bg-surface-2 pr-2 text-xs",
        attachment.status === "error" ? "border-danger/40" : "border-border",
      )}
    >
      {isImage && attachment.previewUrl ? (
        // eslint-disable-next-line @next/next/no-img-element -- local object URL preview, never served by our API
        <img src={attachment.previewUrl} alt="" className="h-10 w-10 shrink-0 rounded-l-lg object-cover" />
      ) : (
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-l-lg bg-surface-3 text-muted">
          <File size={16} />
        </div>
      )}
      <div className="min-w-0 max-w-[140px] py-1">
        <p className="truncate font-medium">{attachment.file.name}</p>
        <p className="truncate text-muted">
          {attachment.status === "error" ? attachment.message : formatBytes(attachment.file.size)}
        </p>
      </div>
      {attachment.status === "uploading" && <Loader2 size={14} className="mr-1 shrink-0 animate-spin text-muted" />}
      {attachment.status === "error" && (
        <button
          type="button"
          onClick={onRetry}
          aria-label={`Retry uploading ${attachment.file.name}`}
          className="shrink-0 rounded p-1 text-muted hover:text-foreground"
        >
          <RotateCcw size={13} />
        </button>
      )}
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${attachment.file.name}`}
        className="shrink-0 rounded p-1 text-muted hover:text-foreground"
      >
        <X size={13} />
      </button>
    </div>
  );
}
