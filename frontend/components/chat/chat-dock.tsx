"use client";

import { ChatResizeHandle } from "@/components/chat/chat-resize-handle";
import { useChatWidget } from "@/components/chat/chat-widget-context";
import { cn } from "@/lib/utils";

/** Renders one of three wrappers around the chat panel depending on
 * ChatWidgetContext's derived `presentation`:
 *  - docked: a sticky, resizable column that's a normal flex sibling of <main> — this is
 *    what makes AppShell's `<main>` actually shrink (no absolute/fixed positioning
 *    involved, unlike the old fixed-popover widget).
 *  - overlay: narrow-viewport fallback — a backdrop + a fixed full-height panel, closer
 *    to a typical mobile chat sheet.
 *  - fullscreen: covers the whole viewport.
 * `--chat-inset` is set on the shell's own root wrapper (components/layout/app-shell.tsx)
 * from `width`/`isOpen` — this component doesn't need to touch it directly. */
export function ChatDock({ children }: { children: React.ReactNode }) {
  const { presentation, width, isResizing, isOpen, close } = useChatWidget();

  if (!isOpen) return null;

  if (presentation === "fullscreen") {
    return <div className="fixed inset-0 z-50 flex flex-col bg-surface">{children}</div>;
  }

  if (presentation === "overlay") {
    return (
      <>
        <div className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm" onClick={close} aria-hidden="true" />
        <div className="fixed inset-y-0 right-0 z-50 my-2 mr-2 flex w-full max-w-[420px] flex-col overflow-hidden rounded-xl border border-border bg-surface shadow-elevation-3">
          {children}
        </div>
      </>
    );
  }

  // docked
  return (
    <aside
      style={{ width }}
      className={cn(
        "relative sticky top-0 flex h-screen shrink-0 flex-col border-l border-border bg-surface",
        !isResizing && "transition-[width] duration-200",
      )}
    >
      <ChatResizeHandle />
      {children}
    </aside>
  );
}
