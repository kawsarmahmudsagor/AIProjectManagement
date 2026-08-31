"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { dismissGithubSuggestion, type GithubSuggestion } from "@/lib/suggestions";

export function SuggestedReposCard({ initialSuggestions }: { initialSuggestions: GithubSuggestion[] }) {
  const [suggestions, setSuggestions] = useState(initialSuggestions);
  const [dismissingId, setDismissingId] = useState<string | null>(null);

  const onDismiss = async (id: string) => {
    setDismissingId(id);
    const previous = suggestions;
    setSuggestions((current) => current.filter((s) => s.id !== id));
    try {
      await dismissGithubSuggestion(id);
    } catch {
      setSuggestions(previous);
    } finally {
      setDismissingId(null);
    }
  };

  return (
    <Card className="h-full">
      <h3 className="font-semibold">Suggested for you</h3>
      {suggestions.length === 0 ? (
        <p className="mt-3 text-sm text-muted">
          No suggestions yet — add technologies to your projects and check back soon.
        </p>
      ) : (
        <ul className="mt-3 space-y-3">
          {suggestions.map((s) => (
            <li key={s.id} className="flex items-start justify-between gap-3 text-sm">
              <div className="min-w-0">
                <a
                  href={s.repo.url}
                  target="_blank"
                  rel="noreferrer"
                  className="truncate font-medium text-accent hover:underline"
                >
                  {s.repo.full_name}
                </a>
                <p className="mt-0.5 text-xs text-muted">
                  {s.technology} &middot; {s.repo.stars.toLocaleString()} stars
                </p>
              </div>
              <Button
                variant="ghost"
                className="shrink-0 px-2 py-1 text-xs"
                disabled={dismissingId === s.id}
                onClick={() => void onDismiss(s.id)}
                aria-label={`Dismiss suggestion: ${s.repo.full_name}`}
              >
                Dismiss
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
