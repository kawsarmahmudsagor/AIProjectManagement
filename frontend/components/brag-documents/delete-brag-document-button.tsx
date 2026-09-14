"use client";

import { Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ConfirmPopover } from "@/components/ui/confirm-popover";
import { useDeleteBragDocumentJob } from "@/hooks/use-brag-document-job";
import { ApiError } from "@/lib/api-client";

export function DeleteBragDocumentButton({ jobId, jobName }: { jobId: string; jobName: string }) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const deleteJob = useDeleteBragDocumentJob(jobId);

  function close() {
    if (deleteJob.isPending) return;
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
  }, [open, deleteJob.isPending]);

  async function handleConfirm() {
    setError(null);
    try {
      await deleteJob.mutateAsync();
      setOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete this brag document.");
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
        aria-label={`Delete ${jobName}`}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <Trash2 size={14} />
      </Button>
      <ConfirmPopover
        open={open}
        title="Delete brag document"
        description={`Delete "${jobName}"? This can't be undone.`}
        confirmLabel="Delete"
        isConfirming={deleteJob.isPending}
        error={error}
        onConfirm={handleConfirm}
        onCancel={close}
      />
    </div>
  );
}
