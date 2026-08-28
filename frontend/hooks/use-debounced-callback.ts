import { useCallback, useEffect, useRef } from "react";

/**
 * Returns `{ run, flush }` rather than a single function with a `.flush` property —
 * this project's ESLint config enforces React Compiler's rules (no mutating `let`s
 * captured by a `useMemo`-returned closure, no ref writes during render), so state
 * lives in refs and is only ever touched inside callbacks/effects, never in the render
 * body itself.
 */
export function useDebouncedCallback<Args extends unknown[]>(fn: (...args: Args) => void, delayMs: number) {
  const fnRef = useRef(fn);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const lastArgsRef = useRef<Args | undefined>(undefined);

  useEffect(() => {
    fnRef.current = fn;
  });

  const flush = useCallback(() => {
    if (timerRef.current === undefined) return;
    clearTimeout(timerRef.current);
    timerRef.current = undefined;
    if (lastArgsRef.current) fnRef.current(...lastArgsRef.current);
  }, []);

  const run = useCallback(
    (...args: Args) => {
      lastArgsRef.current = args;
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        timerRef.current = undefined;
        fnRef.current(...args);
      }, delayMs);
    },
    [delayMs],
  );

  useEffect(() => () => flush(), [flush]);

  return { run, flush };
}
