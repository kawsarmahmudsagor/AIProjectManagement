"use client";

import { Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ConfirmPopover } from "@/components/ui/confirm-popover";

/** Small confirm-gated delete affordance reused for every removable unit in the brag
 * document editor (a bullet, a sub-theme, a whole project group, an impact area) — a
 * lighter/icon-only sibling of DeleteBragDocumentButton's same open/confirm pattern,
 * since here it appears once per item rather than once per page. `label` names the item
 * being removed for the confirmation copy and the button's aria-label. */
export function RemoveIconButton({ label, onConfirm }: { label: string; onConfirm: () => void }) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  function close() {
    setOpen(false);
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
  }, [open]);

  return (
    <div ref={wrapperRef} className="relative inline-block shrink-0">
      <Button
        type="button"
        variant="ghost"
        onClick={() => setOpen(true)}
        className="min-w-0 px-1.5 py-1 text-muted hover:text-danger"
        aria-label={`Remove ${label}`}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <Trash2 size={13} />
      </Button>
      <ConfirmPopover
        open={open}
        title={`Remove ${label}?`}
        description="This can't be undone unless you reset all changes back to the original draft."
        confirmLabel="Remove"
        onConfirm={() => {
          close();
          onConfirm();
        }}
        onCancel={close}
      />
    </div>
  );
}
