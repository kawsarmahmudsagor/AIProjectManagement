"use client";

import { useState } from "react";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { dismissGithubSuggestion, type GithubSuggestion } from "@/lib/suggestions";
import { formatTimestamp } from "@/lib/dates";
import { cn } from "@/lib/utils";

const SOURCE_LABELS: Record<GithubSuggestion["source"], string> = {
  dashboard: "Dashboard",
  chat: "Jarvis",
};

export function SuggestionsSection({ initialSuggestions }: { initialSuggestions: GithubSuggestion[] }) {
  const [suggestions, setSuggestions] = useState(initialSuggestions);
  const [dismissingId, setDismissingId] = useState<string | null>(null);

  async function onDismiss(id: string) {
    setDismissingId(id);
    const previous = suggestions;
    setSuggestions((current) => current.map((s) => (s.id === id ? { ...s, dismissed: true } : s)));
    try {
      await dismissGithubSuggestion(id);
    } catch {
      setSuggestions(previous);
    } finally {
      setDismissingId(null);
    }
  }

  if (suggestions.length === 0) {
    return (
      <p className="text-sm text-muted">
        No suggestions yet — turn on preemptive suggestions in Settings &gt; Chatbot, or ask Jarvis to
        recommend something.
      </p>
    );
  }

  return (
    <Card className="divide-y divide-border p-0">
      {suggestions.map((s) => (
        <div key={s.id} className={cn("flex items-start justify-between gap-3 px-4 py-3", s.dismissed && "opacity-60")}>
          <div className="min-w-0">
            <a
              href={s.repo.url}
              target="_blank"
              rel="noreferrer"
              className="truncate font-medium text-accent hover:underline"
            >
              {s.repo.full_name}
            </a>
            <p className="mt-0.5 line-clamp-1 text-xs text-muted">{s.repo.description}</p>
            <p className="mt-1 text-xs text-muted">
              {s.technology} &middot; {s.repo.stars.toLocaleString()} stars &middot; {SOURCE_LABELS[s.source]} &middot;{" "}
              {formatTimestamp(s.computed_at)}
            </p>
          </div>
          <div className="shrink-0">
            {s.dismissed ? (
              <Badge>Dismissed</Badge>
            ) : (
              <Button
                variant="ghost"
                className="px-2 py-1 text-xs"
                disabled={dismissingId === s.id}
                onClick={() => void onDismiss(s.id)}
                aria-label={`Dismiss suggestion: ${s.repo.full_name}`}
              >
                Dismiss
              </Button>
            )}
          </div>
        </div>
      ))}
    </Card>
  );
}
