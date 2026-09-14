"use client";

import { useRef, useState } from "react";
import { useEnterTransition } from "@/hooks/use-enter-transition";
import { cn } from "@/lib/utils";

/** A small anchored dropdown menu — the inline-popover mechanics already established by
 * components/ui/confirm-popover.tsx (relative wrapper + absolute panel +
 * useEnterTransition, no portal), generalized for "click a trigger, show a list of
 * actions" instead of a single confirm/cancel pair. Used by the sidebar's user menu now;
 * the chat composer's attach-file menu (Images/Documents/Other) is the next consumer.
 *
 * Closes on outside focus via `onBlur` + a `relatedTarget` containment check — no
 * document-level listener to add/remove (matching this codebase's existing preference,
 * see hooks/use-debounced-callback.ts's comment on avoiding refs mutated outside
 * callbacks/effects) — and on Escape via a plain onKeyDown. */
export function Menu({
  trigger,
  children,
  align = "start",
  className,
}: {
  trigger: (props: { onClick: () => void; "aria-expanded": boolean; "aria-haspopup": "menu" }) => React.ReactNode;
  children: React.ReactNode;
  align?: "start" | "end";
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const visible = useEnterTransition(open);
  const wrapperRef = useRef<HTMLDivElement>(null);

  return (
    <div
      ref={wrapperRef}
      className="relative inline-block"
      onBlur={(e) => {
        if (!wrapperRef.current?.contains(e.relatedTarget as Node)) setOpen(false);
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") setOpen(false);
      }}
    >
      {trigger({ onClick: () => setOpen((v) => !v), "aria-expanded": open, "aria-haspopup": "menu" })}
      {open && (
        <div
          role="menu"
          className={cn(
            // z-60 = the documented --z-popover step in globals.css's token scale.
            // Tailwind v4's z-* utilities take plain integers directly (verified: no
            // --z-index-* theme namespace exists to hang named values off), so the scale
            // there is a reference legend and call sites use the matching bare number.
            "absolute z-60 mt-2 min-w-[200px] rounded-xl border border-border bg-surface p-1 shadow-elevation-2 transition duration-150 ease-out motion-reduce:transition-none",
            align === "end" ? "right-0" : "left-0",
            visible ? "scale-100 opacity-100" : "pointer-events-none scale-95 opacity-0",
            className,
          )}
        >
          {children}
        </div>
      )}
    </div>
  );
}

export function MenuItem({
  onClick,
  children,
  className,
}: {
  onClick?: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-foreground hover:bg-surface-2",
        className,
      )}
    >
      {children}
    </button>
  );
}
