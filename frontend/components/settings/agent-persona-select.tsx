"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { AgentPersona } from "@/lib/types";

const LABELS: Record<AgentPersona, string> = {
  business_analyst: "Business Analyst",
  technical_developer: "Technical Developer",
};

/** Which persona frames the system prompt for every AI action — document extraction and
 * every "Enhance with AI" rewrite (backend/app/providers/prompts.py's *_SYSTEM_PROMPTS
 * dicts, keyed by this same value). Defaults to Business Analyst. */
export function AgentPersonaSelect({ initial }: { initial: AgentPersona }) {
  const [value, setValue] = useState<AgentPersona>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onChange = async (next: AgentPersona) => {
    const previous = value;
    setValue(next);
    setSaving(true);
    setError(null);
    try {
      await apiFetch("auth/me", { method: "PATCH", body: JSON.stringify({ agent_persona: next }) });
    } catch (err) {
      setValue(previous);
      setError(err instanceof ApiError ? err.message : "Could not update the agent persona");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="space-y-3">
      <div>
        <h2 className="font-medium">Agent Persona</h2>
        <p className="text-sm text-muted">
          Determines how the AI writes for you — document extraction and every &quot;Enhance with AI&quot; action
          use this persona&apos;s voice.
        </p>
      </div>
      <select
        value={value}
        disabled={saving}
        onChange={(e) => void onChange(e.target.value as AgentPersona)}
        className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none disabled:opacity-60"
      >
        {(Object.keys(LABELS) as AgentPersona[]).map((persona) => (
          <option key={persona} value={persona}>
            {LABELS[persona]}
          </option>
        ))}
      </select>
      {error && <p className="text-sm text-danger">{error}</p>}
    </Card>
  );
}
