"use client";

import { AlertTriangle, CheckCircle2, X } from "lucide-react";
import { createContext, useCallback, useContext, useRef, useState } from "react";
import { cn } from "@/lib/utils";

type Toast = { id: number; variant: "success" | "error"; message: string };
type ToastInput = { variant: "success" | "error"; message: string };

const ToastContext = createContext<((toast: ToastInput) => void) | null>(null);

const AUTO_DISMISS_MS = 5000;

/** Mounted once in app/providers.tsx. Success toasts auto-dismiss; error toasts stay
 * until the user closes them — a failed optimistic mutation that silently rolls back is
 * a data-integrity lie if nothing tells the user it happened. */
export function ToasterProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    ({ variant, message }: ToastInput) => {
      const id = ++idRef.current;
      setToasts((prev) => [...prev.slice(-2), { id, variant, message }]);
      if (variant === "success") {
        setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
      }
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={toast}>
      {children}
      {/* right offset by --chat-inset, set on <html> by app-shell.tsx (this toast
          container is a DOM sibling of AppShell's tree, not a descendant of it — see
          that file's comment on why the variable has to live on a real ancestor of
          both) so a toast never renders underneath the docked chat panel. Falls back to
          0px on pages outside AppShell (e.g. auth), which never set the variable. */}
      <div
        className="pointer-events-none fixed bottom-6 z-70 flex w-80 flex-col gap-2"
        style={{ right: "calc(1.5rem + var(--chat-inset, 0px))" }}
        aria-live="polite"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role={t.variant === "error" ? "alert" : "status"}
            className={cn(
              "pointer-events-auto flex items-start gap-2 rounded-lg border p-3 text-sm shadow-lg",
              t.variant === "error"
                ? "border-danger/40 bg-surface text-foreground"
                : "border-success/40 bg-surface text-foreground",
            )}
          >
            {t.variant === "error" ? (
              <AlertTriangle size={16} className="mt-0.5 shrink-0 text-danger" />
            ) : (
              <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-success" />
            )}
            <p className="flex-1">{t.message}</p>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss"
              className="shrink-0 text-muted hover:text-foreground"
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const toast = useContext(ToastContext);
  if (!toast) throw new Error("useToast must be used within ToasterProvider");
  return { toast };
}
