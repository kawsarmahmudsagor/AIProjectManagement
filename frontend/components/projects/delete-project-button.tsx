"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ConfirmPopover } from "@/components/ui/confirm-popover";
import { PROJECTS_NAV_QUERY_KEY } from "@/components/layout/projects-nav-section";
import { ApiError, apiFetch } from "@/lib/api-client";

export function DeleteProjectButton({
  projectId,
  projectName,
  redirectTo,
  iconOnly = false,
}: {
  projectId: string;
  projectName: string;
  redirectTo?: string;
  iconOnly?: boolean;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
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
      await apiFetch<void>(`projects/${projectId}`, { method: "DELETE" });
      queryClient.invalidateQueries({ queryKey: PROJECTS_NAV_QUERY_KEY });
      setOpen(false);
      if (redirectTo) router.push(redirectTo);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete project.");
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
        className={iconOnly ? "min-w-0 px-2 py-2" : "min-w-[100px]"}
        aria-label={`Delete ${projectName}`}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <Trash2 size={14} />
        {!iconOnly && "Delete"}
      </Button>
      <ConfirmPopover
        open={open}
        title="Delete project"
        description={`Delete "${projectName}"? This can't be undone.`}
        confirmLabel="Delete"
        isConfirming={isDeleting}
        error={error}
        onConfirm={handleConfirm}
        onCancel={close}
      />
    </div>
  );
}
