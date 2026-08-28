"use client";

import { Check, Copy, RotateCcw, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { SuggestionState } from "@/hooks/use-field-suggestion";

export function AiSuggestionPanel({
  state,
  limit,
  onAccept,
  onRetry,
  onDiscard,
}: {
  state: SuggestionState;
  limit: number;
  onAccept: () => void;
  onRetry: () => void;
  onDiscard: () => void;
}) {
  const [copied, setCopied] = useState(false);

  if (state.status === "idle") return null;

  if (state.status === "loading") {
    return (
      <div className="mt-2 flex items-center gap-2 rounded-lg border border-accent/30 bg-accent/5 px-3 py-2 text-sm text-muted">
        <Sparkles size={14} className="animate-pulse text-accent" />
        Thinking…
        <button type="button" onClick={onDiscard} className="ml-auto text-xs text-muted hover:text-foreground">
          Cancel
        </button>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="mt-2 rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm">
        <p className="text-danger">{state.message}</p>
        <div className="mt-2 flex gap-2">
          <Button variant="secondary" onClick={onRetry} className="h-7 px-2 text-xs">
            Try again
          </Button>
          <Button variant="ghost" onClick={onDiscard} className="h-7 px-2 text-xs">
            Dismiss
          </Button>
        </div>
      </div>
    );
  }

  const chars = state.suggestion.text.length;

  const copy = async () => {
    await navigator.clipboard.writeText(state.suggestion.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="mt-2 rounded-lg border border-accent/30 bg-accent/5">
      <div className="flex items-center gap-2 border-b border-accent/20 px-3 py-1.5 text-xs font-medium text-accent">
        <Sparkles size={13} />
        Suggested rewrite
      </div>
      <div
        className="max-h-64 overflow-y-auto px-3 py-2 text-sm prose prose-invert prose-sm max-w-none"
        dangerouslySetInnerHTML={{ __html: state.suggestion.html }}
      />
      {state.overLimit && (
        <p className="px-3 pb-1 text-xs text-danger">
          {chars} / {limit} characters — over the limit. Replace is disabled; try again for a shorter version.
        </p>
      )}
      <div className="flex items-center gap-2 border-t border-accent/20 px-3 py-2">
        <Button onClick={onAccept} disabled={state.overLimit} className="h-7 px-2 text-xs">
          <Check size={13} /> Replace
        </Button>
        <Button variant="secondary" onClick={onRetry} className="h-7 px-2 text-xs">
          <RotateCcw size={13} /> Try again
        </Button>
        <Button variant="ghost" onClick={copy} className="h-7 px-2 text-xs">
          <Copy size={13} /> {copied ? "Copied" : "Copy"}
        </Button>
        <Button variant="ghost" onClick={onDiscard} className="ml-auto h-7 px-2 text-xs">
          <X size={13} /> Discard
        </Button>
      </div>
    </div>
  );
}
