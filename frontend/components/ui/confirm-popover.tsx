"use client";

import { AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Anchored confirmation popover — rendered inline next to its trigger (not a portal),
 * so it visually pops out of the button that opened it. Pair with a `relative` wrapper
 * around the trigger. */
export function ConfirmPopover({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  isConfirming = false,
  error,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  isConfirming?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [visible, setVisible] = useState(false);

  // Reset the entrance transition for next time this opens (render-phase state
  // adjustment, not an effect — see react.dev/learn/you-might-not-need-an-effect).
  const [prevOpen, setPrevOpen] = useState(open);
  if (prevOpen !== open) {
    setPrevOpen(open);
    if (!open) setVisible(false);
  }

  useEffect(() => {
    if (!open) return;
    const raf = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(raf);
  }, [open]);

  if (!open) return null;

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-label={title}
      className={cn(
        "absolute right-0 top-full z-30 mt-2 w-72 origin-top-right rounded-xl border border-border bg-surface p-4 shadow-2xl transition duration-150 ease-out motion-reduce:transition-none",
        visible ? "scale-100 opacity-100" : "pointer-events-none scale-95 opacity-0",
      )}
    >
      <div
        aria-hidden="true"
        className="absolute -top-1.5 right-4 h-3 w-3 rotate-45 border-l border-t border-border bg-surface"
      />
      <div className="flex items-start gap-2.5">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-danger/10 text-danger">
          <AlertTriangle size={16} />
        </div>
        <div>
          <p className="font-medium">{title}</p>
          <p className="mt-0.5 text-sm text-muted">{description}</p>
        </div>
      </div>
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}
      <div className="mt-4 flex justify-end gap-2">
        <Button
          type="button"
          variant="secondary"
          onClick={onCancel}
          disabled={isConfirming}
          className="min-w-0 px-3 py-1.5 text-sm"
        >
          {cancelLabel}
        </Button>
        <Button
          type="button"
          variant="danger"
          onClick={onConfirm}
          disabled={isConfirming}
          className="min-w-[84px] px-3 py-1.5 text-sm"
        >
          {isConfirming ? "Deleting…" : confirmLabel}
        </Button>
      </div>
    </div>
  );
}
