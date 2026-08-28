"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { ChatProvider } from "@/lib/types";

const LABELS: Record<ChatProvider, string> = { gemini: "Google Gemini", ollama: "Ollama (local)" };

/** Which provider drives Jarvis specifically — separate from the "Active provider" used
 * for extraction/rewrite (default-provider-select.tsx). Same optimistic-PATCH-with-
 * rollback shape as agent-persona-select.tsx. */
export function ChatbotProviderSelect({ initial }: { initial: ChatProvider }) {
  const [value, setValue] = useState<ChatProvider>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onChange = async (next: ChatProvider) => {
    const previous = value;
    setValue(next);
    setSaving(true);
    setError(null);
    try {
      await apiFetch("auth/me", { method: "PATCH", body: JSON.stringify({ chat_provider: next }) });
    } catch (err) {
      setValue(previous);
      setError(err instanceof ApiError ? err.message : "Could not update Jarvis's provider");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="space-y-3">
      <div>
        <h2 className="font-medium">Jarvis&apos;s provider</h2>
        <p className="text-sm text-muted">Which AI provider drives Jarvis, the chatbot.</p>
      </div>
      <select
        value={value}
        disabled={saving}
        onChange={(e) => void onChange(e.target.value as ChatProvider)}
        className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none disabled:opacity-60"
      >
        {(Object.keys(LABELS) as ChatProvider[]).map((provider) => (
          <option key={provider} value={provider}>
            {LABELS[provider]}
          </option>
        ))}
      </select>
      {error && <p className="text-sm text-danger">{error}</p>}
    </Card>
  );
}
