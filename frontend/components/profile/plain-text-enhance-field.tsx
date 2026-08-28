"use client";

import { Check, RotateCcw, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { useController, type Control } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { useShowProviderErrorModal } from "@/components/layout/provider-error-modal";
import { ApiError } from "@/lib/api-client";
import { enhanceProfileField, type EnhanceableField } from "@/lib/profile";
import type { ProfileFormValues } from "@/lib/profile-schema";

/** The lighter equivalent of DualEditorField/AiSuggestionPanel for the Profile page's
 * bio fields — these are plain text (no Tiptap toolbar, unlike project description
 * fields), so this is a plain textarea + a simplified inline suggestion panel rather
 * than reusing the RichText-specific components. Same hard rule though: the suggestion
 * is never written into the field without an explicit Accept. */
export function PlainTextEnhanceField({
  name,
  label,
  limit,
  placeholder,
  control,
}: {
  name: keyof ProfileFormValues;
  label: string;
  limit: number;
  placeholder: string;
  control: Control<ProfileFormValues>;
}) {
  const { field } = useController({ name, control });
  const value = (field.value as string | undefined) ?? "";

  type SuggestionState =
    | { status: "idle" }
    | { status: "loading" }
    | { status: "ready"; text: string }
    | { status: "error"; message: string };
  const [suggestion, setSuggestion] = useState<SuggestionState>({ status: "idle" });
  const showProviderError = useShowProviderErrorModal();

  const run = async () => {
    setSuggestion({ status: "loading" });
    try {
      const text = await enhanceProfileField({
        field: name as EnhanceableField,
        target_text: value,
      });
      setSuggestion({ status: "ready", text });
    } catch (err) {
      if (err instanceof ApiError && showProviderError({ code: err.code, provider: err.provider })) {
        setSuggestion({ status: "idle" });
        return;
      }
      setSuggestion({ status: "error", message: err instanceof Error ? err.message : "Something went wrong" });
    }
  };

  const accept = () => {
    if (suggestion.status !== "ready") return;
    field.onChange(suggestion.text);
    setSuggestion({ status: "idle" });
  };

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <label className="text-sm font-medium">{label}</label>
        <Button type="button" variant="ghost" onClick={() => void run()} disabled={suggestion.status === "loading"} className="h-7 px-2 text-xs">
          <Sparkles size={13} /> Enhance with AI
        </Button>
      </div>
      <textarea
        value={value}
        onChange={(e) => field.onChange(e.target.value)}
        onBlur={field.onBlur}
        placeholder={placeholder}
        rows={3}
        className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/50"
      />
      <p className="mt-1 text-right text-xs text-muted">
        {value.length}/{limit}
      </p>

      {suggestion.status === "loading" && (
        <div className="ai-glow ai-glow--generating mt-2 flex items-center gap-2 rounded-lg border border-accent/30 bg-accent/5 px-3 py-2 text-sm text-muted">
          <Sparkles size={14} className="animate-pulse text-accent" />
          Thinking…
        </div>
      )}

      {suggestion.status === "error" && (
        <div className="mt-2 rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm">
          <p className="text-danger">{suggestion.message}</p>
          <div className="mt-2 flex gap-2">
            <Button type="button" variant="secondary" onClick={() => void run()} className="h-7 px-2 text-xs">
              Try again
            </Button>
            <Button type="button" variant="ghost" onClick={() => setSuggestion({ status: "idle" })} className="h-7 px-2 text-xs">
              Dismiss
            </Button>
          </div>
        </div>
      )}

      {suggestion.status === "ready" && (
        <div className="mt-2 rounded-lg border border-accent/30 bg-accent/5">
          <div className="flex items-center gap-2 border-b border-accent/20 px-3 py-1.5 text-xs font-medium text-accent">
            <Sparkles size={13} /> Suggested rewrite
          </div>
          <p className="max-h-40 overflow-y-auto px-3 py-2 text-sm">{suggestion.text}</p>
          {suggestion.text.length > limit && (
            <p className="px-3 pb-1 text-xs text-danger">
              {suggestion.text.length} / {limit} characters — over the limit. Replace is disabled; try again for a
              shorter version.
            </p>
          )}
          <div className="flex items-center gap-2 border-t border-accent/20 px-3 py-2">
            <Button type="button" onClick={accept} disabled={suggestion.text.length > limit} className="h-7 px-2 text-xs">
              <Check size={13} /> Replace
            </Button>
            <Button type="button" variant="secondary" onClick={() => void run()} className="h-7 px-2 text-xs">
              <RotateCcw size={13} /> Try again
            </Button>
            <Button type="button" variant="ghost" onClick={() => setSuggestion({ status: "idle" })} className="ml-auto h-7 px-2 text-xs">
              <X size={13} /> Discard
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
