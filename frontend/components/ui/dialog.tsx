"use client";

import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

/** A real modal dialog built on the native <dialog> element rather than hand-rolled
 * `fixed inset-0` + manual keydown/focus-trap logic — this app has no Radix/Base UI
 * (see frontend/AGENTS.md), and three separate components had each hand-rolled their own
 * modal before this (components/layout/provider-error-modal.tsx,
 * components/projects/ai/ai-enhance-context-dialog.tsx, and the project-form "Input"
 * dialog). `showModal()` gives focus trapping, Escape-to-close, ::backdrop, and
 * scroll-blocking for free — a from-scratch focus trap is exactly the kind of thing that
 * ships subtly broken, so this is the pragmatic answer to having no headless dep.
 *
 * Usage: control visibility with the `open` prop like any other component — this
 * wrapper translates that into imperative `showModal()`/`close()` calls itself, so
 * callers never touch the DOM API directly. */
export function Dialog({
  open,
  onClose,
  title,
  children,
  className,
  "aria-label": ariaLabel,
}: {
  open: boolean;
  onClose: () => void;
  /** Rendered in the header next to the close button. Omit for a dialog that draws its
   * own header (pass `aria-label` instead so it's still announced correctly). */
  title?: string;
  children: React.ReactNode;
  className?: string;
  "aria-label"?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  // The native "cancel" event fires on Escape — sync it back into the controlled `open`
  // state rather than letting the dialog close itself out from under the caller.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onCancel = (e: Event) => {
      e.preventDefault();
      onClose();
    };
    // Clicking the ::backdrop closes native <dialog> only if the app wires it — this app
    // wires it explicitly below via onClick on the dialog element checking the click
    // target, since <dialog> has no built-in "click outside" event.
    el.addEventListener("cancel", onCancel);
    return () => el.removeEventListener("cancel", onCancel);
  }, [onClose]);

  return (
    <dialog
      ref={ref}
      aria-label={ariaLabel ?? title}
      onClick={(e) => {
        if (e.target === ref.current) onClose(); // clicked the ::backdrop, not the panel
      }}
      onClose={onClose}
      className={cn(
        "m-auto w-full max-w-md rounded-xl border border-border bg-surface p-0 shadow-elevation-2",
        "backdrop:bg-black/60",
        className,
      )}
    >
      {title && (
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-sm font-medium">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1 text-muted hover:bg-surface-2 hover:text-foreground"
          >
            <X size={16} />
          </button>
        </div>
      )}
      <div className={title ? "p-4" : undefined} onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </dialog>
  );
}
