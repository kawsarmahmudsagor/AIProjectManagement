"use client";

import { useCallback, useSyncExternalStore } from "react";

/** `useSyncExternalStore` rather than a `useState` + effect: the effect version renders
 * one frame with the wrong answer before the subscription fires (this app already
 * prefers render-phase/derived state over sync effects — see the comments at
 * components/projects/upload/document-upload.tsx:71-75 and hooks/use-chat-stream.ts:52-58).
 * `serverDefault` is what SSR/the very first client render sees before hydration can
 * safely call `window.matchMedia` — callers should pick a value that can't cause a
 * visible flash (e.g. assume desktop for a chat-docking breakpoint, since the panel
 * starts closed and there is nothing to lay out differently until it opens). */
export function useMediaQuery(query: string, serverDefault = false): boolean {
  const subscribe = useCallback(
    (callback: () => void) => {
      const mql = window.matchMedia(query);
      mql.addEventListener("change", callback);
      return () => mql.removeEventListener("change", callback);
    },
    [query],
  );

  const getSnapshot = useCallback(() => window.matchMedia(query).matches, [query]);
  const getServerSnapshot = useCallback(() => serverDefault, [serverDefault]);

  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
