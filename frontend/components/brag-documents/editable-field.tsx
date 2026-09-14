"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

const FIELD_CLASSES =
  "w-full rounded-md border border-transparent bg-transparent px-1.5 py-1 outline-none transition-colors hover:border-border focus:border-accent focus:bg-surface-2/40";

/** Single-line inline-editable text (project name, sub-theme heading, impact category).
 * Local draft state so keystrokes don't fire a save each time — `onCommit` only runs on
 * blur, and only when the value actually changed, so clicking through fields without
 * editing them never triggers a network call. */
export function EditableLine({
  value,
  onCommit,
  placeholder,
  className,
}: {
  value: string;
  onCommit: (next: string) => void;
  placeholder?: string;
  className?: string;
}) {
  const [draft, setDraft] = useState(value);
  // Render-phase "reset state when a prop changes" (react.dev/learn/you-might-not-need-an-effect#adjusting-state-when-a-prop-changes),
  // same technique as ConfirmPopover's own prevOpen tracking — not an effect, since this
  // only needs to run during the render that receives a genuinely new `value` (e.g. a
  // reset, or switching documents), never after our own onBlur commit already matches it.
  const [prevValue, setPrevValue] = useState(value);
  if (prevValue !== value) {
    setPrevValue(value);
    setDraft(value);
  }

  return (
    <input
      type="text"
      value={draft}
      placeholder={placeholder}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => {
        if (draft !== value) onCommit(draft);
      }}
      className={cn(FIELD_CLASSES, "text-sm", className)}
    />
  );
}

/** Multi-line inline-editable text (bullets, key-contribution/impact summaries) —
 * auto-grows to fit its content instead of showing a scrollbar. Same draft/blur-commit
 * behavior as EditableLine. */
export function EditableParagraph({
  value,
  onCommit,
  placeholder,
  className,
}: {
  value: string;
  onCommit: (next: string) => void;
  placeholder?: string;
  className?: string;
}) {
  const [draft, setDraft] = useState(value);
  const ref = useRef<HTMLTextAreaElement>(null);

  const [prevValue, setPrevValue] = useState(value);
  if (prevValue !== value) {
    setPrevValue(value);
    setDraft(value);
  }

  // A real effect (not state-derivation): synchronizes the DOM element's height with
  // whatever the textarea currently displays.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [draft]);

  return (
    <textarea
      ref={ref}
      rows={1}
      value={draft}
      placeholder={placeholder}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => {
        if (draft !== value) onCommit(draft);
      }}
      className={cn(FIELD_CLASSES, "resize-none overflow-hidden text-sm leading-normal", className)}
    />
  );
}
