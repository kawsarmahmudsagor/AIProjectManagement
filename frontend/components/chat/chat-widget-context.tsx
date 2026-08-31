"use client";

import { createContext, useContext, useMemo, useState } from "react";

type ChatWidgetContextValue = {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;
};

const ChatWidgetContext = createContext<ChatWidgetContextValue | null>(null);

/** Owns the floating chat widget's open/closed state at the AppShell level (rather than
 * inside ChatWidget itself) so other pages — e.g. the Conversations page's "resume this
 * conversation" action — can pop the widget open without prop-drilling through layout. */
export function ChatWidgetProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);

  const value = useMemo<ChatWidgetContextValue>(
    () => ({
      isOpen,
      open: () => setIsOpen(true),
      close: () => setIsOpen(false),
      toggle: () => setIsOpen((v) => !v),
    }),
    [isOpen],
  );

  return <ChatWidgetContext.Provider value={value}>{children}</ChatWidgetContext.Provider>;
}

export function useChatWidget(): ChatWidgetContextValue {
  const ctx = useContext(ChatWidgetContext);
  if (!ctx) throw new Error("useChatWidget must be used within a ChatWidgetProvider");
  return ctx;
}
