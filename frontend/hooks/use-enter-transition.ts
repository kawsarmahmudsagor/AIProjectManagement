"use client";

import { useEffect, useState } from "react";

/** The "mount closed, flip to visible on the next frame so the CSS transition actually
 * plays instead of snapping" pattern — previously duplicated verbatim in
 * components/ui/confirm-popover.tsx and components/chat/chat-panel.tsx. Both call sites
 * also needed a render-phase reset (matching react.dev's
 * you-might-not-need-an-effect guidance) for the case where `open` toggles closed then
 * open again before the exit transition finishes; this hook does that internally so
 * callers don't have to reimplement the `prevOpen` dance themselves.
 *
 * `open === undefined` (the always-mounted case, e.g. chat-panel.tsx which is only
 * rendered at all while open) skips the reset logic — there is nothing to reset back to
 * on remount since the component doesn't unmount/remount on close. */
export function useEnterTransition(open?: boolean): boolean {
  const [visible, setVisible] = useState(false);

  const [prevOpen, setPrevOpen] = useState(open);
  if (open !== undefined && prevOpen !== open) {
    setPrevOpen(open);
    if (!open) setVisible(false);
  }

  useEffect(() => {
    if (open === false) return;
    const raf = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(raf);
  }, [open]);

  return visible;
}
