"use client";

import { createContext, useCallback, useContext, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { providerErrorKind, providerErrorMessage } from "@/lib/provider-errors";

type ProviderErrorInput = { code?: string; provider?: string | null };

/** Returns true if `error` matched a known provider-limit/expired code and the popup
 * was shown — callers can use this to skip their own inline error handling for it. */
type ShowProviderError = (error: ProviderErrorInput) => boolean;

const ProviderErrorModalContext = createContext<ShowProviderError | null>(null);

/** Mounted once in app/providers.tsx so any code path that surfaces a backend error —
 * the extraction-job poll, the AI rewrite call, anything added later — can pop this
 * without threading modal state through every component in between. */
export function ProviderErrorModalProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<{ kind: "limit" | "expired"; provider?: string | null } | null>(null);

  const show = useCallback<ShowProviderError>((error) => {
    const kind = providerErrorKind(error.code);
    if (!kind) return false;
    setState({ kind, provider: error.provider });
    return true;
  }, []);

  const dismiss = () => setState(null);

  return (
    <ProviderErrorModalContext.Provider value={show}>
      {children}
      {state && (
        <div
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="provider-error-message"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={dismiss}
        >
          <Card
            className="w-full max-w-sm space-y-4 text-center shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-4xl" aria-hidden="true">
              {state.kind === "expired" ? "😅" : "💳"}
            </p>
            <p id="provider-error-message" className="text-sm font-medium">
              {providerErrorMessage(state.kind, state.provider)}
            </p>
            <Button type="button" onClick={dismiss} className="w-full">
              Got it
            </Button>
          </Card>
        </div>
      )}
    </ProviderErrorModalContext.Provider>
  );
}

/** Call with a backend error's {code, provider}; returns whether it matched and the
 * popup was shown, so the caller can skip its own inline error path for it. */
export function useShowProviderErrorModal(): ShowProviderError {
  const show = useContext(ProviderErrorModalContext);
  if (!show) throw new Error("useShowProviderErrorModal must be used within ProviderErrorModalProvider");
  return show;
}
