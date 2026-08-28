"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { apiFetch, ApiError } from "@/lib/api-client";

export function PreemptiveSuggestionsToggle({ initial }: { initial: boolean }) {
  const [value, setValue] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onChange = async (next: boolean) => {
    const previous = value;
    setValue(next);
    setSaving(true);
    setError(null);
    try {
      await apiFetch("auth/me", {
        method: "PATCH",
        body: JSON.stringify({ chatbot_preemptive_github_suggestions: next }),
      });
    } catch (err) {
      setValue(previous);
      setError(err instanceof ApiError ? err.message : "Could not update this setting");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="flex items-center justify-between gap-4">
      <div>
        <h2 className="font-medium">Preemptive suggestions</h2>
        <p className="text-sm text-muted">
          When on, Jarvis may proactively mention a relevant GitHub repo during a conversation. When off, it
          only searches GitHub when you explicitly ask for a recommendation.
        </p>
        {error && <p className="mt-1 text-sm text-danger">{error}</p>}
      </div>
      <Switch checked={value} onCheckedChange={(next) => void onChange(next)} disabled={saving} aria-label="Preemptive suggestions" />
    </Card>
  );
}
