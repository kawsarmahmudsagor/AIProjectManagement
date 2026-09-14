"use client";

import { useCallback, useSyncExternalStore } from "react";

const STORAGE_KEY = "aipm.sidebar.collapsed";

// A tiny in-module pub-sub, not just `window.addEventListener("storage", ...)`: the
// native "storage" event only fires in OTHER tabs/windows, never the one that made the
// write — without this, toggling collapse in this same tab wouldn't re-render until some
// other trigger happened to run. useSyncExternalStore (not useState+useEffect) is what
// this codebase's react-hooks/set-state-in-effect lint rule actually wants for "read an
// external source, possibly correct initial state" — see hooks/use-media-query.ts for
// the same pattern applied to matchMedia.
const listeners = new Set<() => void>();

function readStored(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false; // private browsing / blocked site data — default to expanded
  }
}

function writeStored(next: boolean) {
  try {
    localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
  } catch {
    // Best effort — in-memory state (still updated via notify() below) covers this tab.
  }
  listeners.forEach((l) => l());
}

function subscribe(callback: () => void): () => void {
  listeners.add(callback);
  window.addEventListener("storage", callback);
  return () => {
    listeners.delete(callback);
    window.removeEventListener("storage", callback);
  };
}

/** Sidebar collapse state was plain `useState(false)` before (no persistence at all,
 * defaulting to expanded every reload). `getServerSnapshot` returns `false` so SSR and
 * the first client render agree — the real stored value (if collapsed) applies on the
 * next render once useSyncExternalStore's subscription resolves, the same one-frame
 * tradeoff the chat dock's own persisted width makes. */
export function usePersistedCollapse(): [boolean, (next: boolean) => void] {
  const collapsed = useSyncExternalStore(subscribe, readStored, () => false);
  const update = useCallback((next: boolean) => writeStored(next), []);
  return [collapsed, update];
}
