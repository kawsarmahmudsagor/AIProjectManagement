"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api-client";
import { deleteChatAttachment, uploadChatAttachment, validateAttachment } from "@/lib/chat-attachments";
import type { ChatAttachment } from "@/lib/types";
import { useToast } from "@/components/ui/toaster";

export type DraftAttachment = {
  localId: string;
  file: File;
  previewUrl?: string; // images only — an object URL for the chip's thumbnail
} & (
  | { status: "uploading"; controller: AbortController }
  | { status: "ready"; remote: ChatAttachment }
  | { status: "error"; message: string }
);

/** Pre-uploads on selection (matching components/profile/photo-upload.tsx and
 * components/projects/upload/document-upload.tsx's immediate-upload pattern) so
 * `send()` stays a JSON body carrying only ids — see lib/chat-attachments.ts's module
 * docstring for why pre-upload-then-reference beats a multipart message endpoint. */
export function useChatAttachments(sessionId: string | null) {
  const [items, setItems] = useState<DraftAttachment[]>([]);
  const { toast } = useToast();
  const itemsRef = useRef(items);

  // Mirrors `items` into a ref for use inside callbacks/cleanup below — writing a ref
  // during render is disallowed (React Compiler's react-hooks/refs rule), so this runs
  // as its own effect (no dependency array: after every render) purely to keep the ref
  // current, never to trigger a re-render itself.
  useEffect(() => {
    itemsRef.current = items;
  });

  useEffect(() => {
    return () => {
      for (const item of itemsRef.current) {
        if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
      }
    };
  }, []);

  const add = useCallback(
    (files: File[]) => {
      if (!sessionId) return;
      for (const file of files) {
        const validationError = validateAttachment(file, itemsRef.current.length);
        if (validationError) {
          toast({ variant: "error", message: validationError });
          continue;
        }

        const localId = crypto.randomUUID();
        const previewUrl = file.type.startsWith("image/") ? URL.createObjectURL(file) : undefined;
        const controller = new AbortController();
        const draft: DraftAttachment = { localId, file, previewUrl, status: "uploading", controller };
        setItems((prev) => [...prev, draft]);

        uploadChatAttachment(sessionId, file, controller.signal)
          .then((remote) => {
            setItems((prev) =>
              prev.map((it) => (it.localId === localId ? { localId, file, previewUrl, status: "ready", remote } : it)),
            );
          })
          .catch((err) => {
            if (err instanceof DOMException && err.name === "AbortError") return;
            const message = err instanceof ApiError ? err.message : "Upload failed";
            setItems((prev) => (prev.some((it) => it.localId === localId) ? prev.map((it) => (it.localId === localId ? { localId, file, previewUrl, status: "error", message } : it)) : prev));
          });
      }
    },
    [sessionId, toast],
  );

  const remove = useCallback((localId: string) => {
    setItems((prev) => {
      const item = prev.find((it) => it.localId === localId);
      if (item) {
        if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
        if (item.status === "uploading") item.controller.abort();
        if (item.status === "ready") void deleteChatAttachment(item.remote.id).catch(() => {});
      }
      return prev.filter((it) => it.localId !== localId);
    });
  }, []);

  const retry = useCallback(
    (localId: string) => {
      const item = itemsRef.current.find((it) => it.localId === localId);
      if (!item) return;
      remove(localId);
      add([item.file]);
    },
    [add, remove],
  );

  const clear = useCallback(() => {
    for (const item of itemsRef.current) {
      if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
    }
    setItems([]);
  }, []);

  const readyIds = items.filter((it): it is DraftAttachment & { status: "ready" } => it.status === "ready").map((it) => it.remote.id);
  const hasPending = items.some((it) => it.status === "uploading");

  return { items, add, remove, retry, clear, readyIds, hasPending };
}
