"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ConfirmPopover } from "@/components/ui/confirm-popover";
import { ApiError } from "@/lib/api-client";
import { deleteChatSession } from "@/lib/chat";

export function DeleteConversationButton({
  sessionId,
  sessionTitle,
}: {
  sessionId: string;
  sessionTitle: string;
}) {
  const router = useRouter();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function close() {
    if (isDeleting) return;
    setOpen(false);
    setError(null);
  }

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(e: PointerEvent) {
      if (!wrapperRef.current?.contains(e.target as Node)) close();
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, isDeleting]);

  async function handleConfirm() {
    setIsDeleting(true);
    setError(null);
    try {
      await deleteChatSession(sessionId);
      setOpen(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete conversation.");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div
      ref={wrapperRef}
      className="relative inline-block"
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
    >
      <Button
        type="button"
        variant="danger"
        onClick={() => {
          setError(null);
          setOpen(true);
        }}
        className="min-w-0 px-2 py-2"
        aria-label={`Delete ${sessionTitle}`}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <Trash2 size={14} />
      </Button>
      <ConfirmPopover
        open={open}
        title="Delete conversation"
        description={`Delete "${sessionTitle}"? This can't be undone.`}
        confirmLabel="Delete"
        isConfirming={isDeleting}
        error={error}
        onConfirm={handleConfirm}
        onCancel={close}
      />
    </div>
  );
}
