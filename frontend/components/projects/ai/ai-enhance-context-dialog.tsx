"use client";

import { Sparkles } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/** Shown for every "Enhance with AI" click before the request goes out, so the user can
 * steer the rewrite (e.g. "I led the model training pipeline and testing, emphasize
 * that") instead of only ever getting the default generic pass. Submitting with the box
 * left empty runs the enhancement exactly as before this dialog existed. */
export function AiEnhanceContextDialog({
  actionLabel,
  onCancel,
  onSubmit,
}: {
  actionLabel: string;
  onCancel: () => void;
  onSubmit: (instruction?: string) => void;
}) {
  const [value, setValue] = useState("");

  const submit = () => onSubmit(value.trim() || undefined);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="ai-enhance-context-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onCancel}
    >
      <Card
        className="ai-glow ai-glow--generating w-full max-w-md space-y-3 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-accent" />
          <h2 id="ai-enhance-context-title" className="text-sm font-medium">
            {actionLabel}
          </h2>
        </div>
        <p className="text-xs text-muted">
          Optionally tell the AI what to focus on or change. Leave this blank to enhance the text as usual.
        </p>
        <textarea
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
            if (e.key === "Escape") onCancel();
          }}
          placeholder="e.g. My role was developing the model training pipeline and testing — update this based on that"
          rows={4}
          className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent"
        />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onCancel} className="h-8 px-3 text-xs">
            Cancel
          </Button>
          <Button type="button" onClick={submit} className="h-8 px-3 text-xs">
            <Sparkles size={13} /> Enhance
          </Button>
        </div>
      </Card>
    </div>
  );
}
