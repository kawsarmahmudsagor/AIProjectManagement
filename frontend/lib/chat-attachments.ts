import { apiFetch } from "@/lib/api-client";
import { MAX_UPLOAD_SIZE_MB } from "@/lib/documents";
import type { ChatAttachment } from "@/lib/types";

export const MAX_ATTACHMENTS_PER_MESSAGE = 5;
export const IMAGE_ACCEPT = "image/jpeg,image/png,image/webp,image/gif";
// .csv/.xlsx/.pptx are deliberately NOT here — the backend's chat attachment sniffer
// only accepts what ingest() already handles (PDF/DOCX/text/code); .xlsx specifically is
// rejected with a message pointing at the Brag Documents page (backend/app/services/
// chat_service.py's save_attachment docstring).
export const DOCUMENT_ACCEPT = ".pdf,.docx,.txt,.md,.py,.ts,.tsx,.js,.jsx,.json,.yaml,.yml,.sql,.html,.css";

export type ChatAttachmentKind = "image" | "document" | "other";

export function classifyFile(file: File): ChatAttachmentKind {
  if (file.type.startsWith("image/")) return "image";
  return "document";
}

export function validateAttachment(file: File, currentCount: number): string | null {
  if (currentCount >= MAX_ATTACHMENTS_PER_MESSAGE) {
    return `You can attach up to ${MAX_ATTACHMENTS_PER_MESSAGE} files per message.`;
  }
  const kind = classifyFile(file);
  const maxMb = kind === "image" ? 5 : MAX_UPLOAD_SIZE_MB;
  if (file.size > maxMb * 1024 * 1024) {
    return `${file.name} is larger than the ${maxMb}MB limit.`;
  }
  return null;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export async function uploadChatAttachment(
  sessionId: string,
  file: File,
  signal?: AbortSignal,
): Promise<ChatAttachment> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<ChatAttachment>(`chat/sessions/${sessionId}/attachments`, {
    method: "POST",
    body: form,
    signal,
  });
}

export async function deleteChatAttachment(attachmentId: string): Promise<void> {
  await apiFetch<void>(`chat/attachments/${attachmentId}`, { method: "DELETE" });
}
