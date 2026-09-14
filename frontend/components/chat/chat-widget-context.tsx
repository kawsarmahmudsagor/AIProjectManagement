"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { useMediaQuery } from "@/hooks/use-media-query";

export type ChatPresentation = "docked" | "overlay" | "fullscreen";

export const MIN_CHAT_WIDTH = 360;
export const MAX_CHAT_WIDTH = 720;
export const DEFAULT_CHAT_WIDTH = 480;
// The main content column is never squeezed narrower than this, regardless of how wide
// the chat panel itself is allowed to grow.
const MIN_MAIN_WIDTH = 480;
const WIDTH_STORAGE_KEY = "aipm.chat.width";

type ChatWidgetContextValue = {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;
  /** Opens the panel with `text` pre-filled in the composer — the dashboard search's
   * "Continue in chat" action. */
  openWithPrompt: (text: string) => void;
  draftText: string;
  setDraftText: (v: string) => void;
  width: number;
  setWidth: (px: number) => void;
  isResizing: boolean;
  setResizing: (v: boolean) => void;
  isFullScreen: boolean;
  toggleFullScreen: () => void;
  /** Derived, not stored: fullscreen wins if set; otherwise docked on a wide viewport,
   * overlay below that breakpoint (a real side-by-side dock has no room to be useful on
   * a narrow screen). */
  presentation: ChatPresentation;
};

const ChatWidgetContext = createContext<ChatWidgetContextValue | null>(null);

function readStoredWidth(): number {
  // Never called during the initial (SSR-matching) render — see the comment on
  // useState's lazy initializer below for why that's safe here specifically, unlike
  // hooks/use-persisted-collapse.ts (which had to move to useSyncExternalStore because
  // ITS value affects the very first render's DOM output). The chat panel only ever
  // renders while `isOpen`, which always starts false, so `width` cannot affect
  // anything in the SSR-vs-hydration first paint.
  try {
    const raw = localStorage.getItem(WIDTH_STORAGE_KEY);
    const parsed = raw ? Number(raw) : NaN;
    return Number.isFinite(parsed) ? parsed : DEFAULT_CHAT_WIDTH;
  } catch {
    return DEFAULT_CHAT_WIDTH;
  }
}

/** Owns the floating chat widget's open/closed state at the AppShell level (rather than
 * inside ChatWidget itself) so other pages — e.g. the Conversations page's "resume this
 * conversation" action, or the dashboard search bar's "continue in chat" — can pop the
 * widget open without prop-drilling through layout. */
export function ChatWidgetProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [draftText, setDraftText] = useState("");
  // Lazy initializer, not a mount effect: this only runs once, on first render, and its
  // value never reaches the DOM until isOpen flips true (a later, purely client-side
  // interaction) — see readStoredWidth's comment.
  const [width, setWidthState] = useState(readStoredWidth);
  const [isResizing, setResizing] = useState(false);
  const [isFullScreen, setIsFullScreen] = useState(false);

  // Assume desktop server-side (serverDefault=true) — the panel starts closed, so a
  // wrong initial guess here has nothing to visibly correct once corrected.
  const isWide = useMediaQuery("(min-width: 1024px)", true);

  const setWidth = useCallback((px: number) => {
    const clamped = Math.min(Math.max(px, MIN_CHAT_WIDTH), MAX_CHAT_WIDTH, window.innerWidth - MIN_MAIN_WIDTH);
    setWidthState(clamped);
    try {
      localStorage.setItem(WIDTH_STORAGE_KEY, String(clamped));
    } catch {
      // Best effort — in-memory width still applies for this tab.
    }
  }, []);

  const presentation: ChatPresentation = isFullScreen ? "fullscreen" : isWide ? "docked" : "overlay";

  const value = useMemo<ChatWidgetContextValue>(
    () => ({
      isOpen,
      open: () => setIsOpen(true),
      close: () => setIsOpen(false),
      toggle: () => setIsOpen((v) => !v),
      openWithPrompt: (text: string) => {
        setDraftText(text);
        setIsOpen(true);
      },
      draftText,
      setDraftText,
      width,
      setWidth,
      isResizing,
      setResizing,
      isFullScreen,
      toggleFullScreen: () => setIsFullScreen((v) => !v),
      presentation,
    }),
    [isOpen, draftText, width, setWidth, isResizing, isFullScreen, presentation],
  );

  return <ChatWidgetContext.Provider value={value}>{children}</ChatWidgetContext.Provider>;
}

export function useChatWidget(): ChatWidgetContextValue {
  const ctx = useContext(ChatWidgetContext);
  if (!ctx) throw new Error("useChatWidget must be used within a ChatWidgetProvider");
  return ctx;
}
