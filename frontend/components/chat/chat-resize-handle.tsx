"use client";

import { useChatWidget } from "@/components/chat/chat-widget-context";

/** Pointer Events + pointer capture — no document-level listeners to add/remove, and no
 * ref mutated outside a callback/effect (this codebase's React Compiler lint rules,
 * see hooks/use-debounced-callback.ts's comment, forbid exactly that pattern). Dragging
 * from the right edge of the viewport shrinks the panel (moving left = wider), since the
 * panel is docked to the right side. */
export function ChatResizeHandle() {
  const { width, setWidth, isResizing, setResizing } = useChatWidget();

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize chat panel"
      aria-valuenow={width}
      tabIndex={0}
      onPointerDown={(e) => {
        e.currentTarget.setPointerCapture(e.pointerId);
        setResizing(true);
      }}
      onPointerMove={(e) => {
        if (!isResizing) return;
        setWidth(window.innerWidth - e.clientX);
      }}
      onPointerUp={(e) => {
        e.currentTarget.releasePointerCapture(e.pointerId);
        setResizing(false);
      }}
      onKeyDown={(e) => {
        if (e.key === "ArrowLeft") setWidth(width + 24);
        if (e.key === "ArrowRight") setWidth(width - 24);
      }}
      className="absolute left-0 top-0 z-10 h-full w-1.5 -translate-x-1/2 cursor-col-resize touch-none bg-transparent transition-colors hover:bg-accent/40 focus-visible:bg-accent/60"
    />
  );
}
