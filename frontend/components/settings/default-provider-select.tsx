"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { ProviderSetting } from "@/lib/types";

type Provider = "gemini" | "openai";

const LABELS: Record<Provider, string> = { gemini: "Google Gemini", openai: "OpenAI" };

/** Which provider document extraction and every "Enhance with AI" action use when no
 * per-request override is given — backend/app/providers/registry.py's
 * resolve_default_provider() reads this same `is_default` flag, so this dropdown is the
 * single switch for "which LLM does the work" across the whole app. */
export function DefaultProviderSelect({ initial }: { initial: ProviderSetting[] }) {
  const [value, setValue] = useState<Provider>(initial.find((s) => s.is_default)?.provider ?? "gemini");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onChange = async (next: Provider) => {
    const previous = value;
    setValue(next);
    setSaving(true);
    setError(null);
    try {
      await apiFetch(`ai-settings/${next}`, { method: "PUT", body: JSON.stringify({ is_default: true }) });
    } catch (err) {
      setValue(previous);
      setError(err instanceof ApiError ? err.message : "Could not update the active provider");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="space-y-3">
      <div>
        <h2 className="font-medium">Active provider</h2>
        <p className="text-sm text-muted">
          Used for document extraction and every &quot;Enhance with AI&quot; action, unless you pick a specific
          provider for a single request. Make sure the provider below has a working connection first.
        </p>
      </div>
      <select
        value={value}
        disabled={saving}
        onChange={(e) => void onChange(e.target.value as Provider)}
        className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none disabled:opacity-60"
      >
        {(Object.keys(LABELS) as Provider[]).map((provider) => (
          <option key={provider} value={provider}>
            {LABELS[provider]}
          </option>
        ))}
      </select>
      {error && <p className="text-sm text-danger">{error}</p>}
    </Card>
  );
}
