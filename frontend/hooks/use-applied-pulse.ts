"use client";

import { useEffect, useRef, useState } from "react";

/** How long the "applied" glow pulse plays after an AI suggestion is accepted into a
 * box — long enough to notice, short enough to not linger and read as "still AI's".
 * Extracted verbatim from components/projects/fields/dual-editor-field.tsx so the
 * project-thumbnail generator and the dashboard search "ask Jarvis" row can share it
 * instead of re-declaring their own copy (a third copy of this exact 15-line timer is
 * what components/profile/plain-text-enhance-field.tsx's own inline duplicate already
 * warned against). */
export const APPLIED_GLOW_MS = 1600;

export function useAppliedPulse(): [boolean, () => void] {
  const [applied, setApplied] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => clearTimeout(timeoutRef.current), []);

  const trigger = () => {
    setApplied(true);
    clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setApplied(false), APPLIED_GLOW_MS);
  };

  return [applied, trigger];
}
