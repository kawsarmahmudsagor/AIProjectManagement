"use client";

import { Sparkles } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";

/** Shown for every "Enhance with AI" click before the request goes out, so the user can
 * steer the rewrite (e.g. "I led the model training pipeline and testing, emphasize
 * that") instead of only ever getting the default generic pass. Submitting with the box
 * left empty runs the enhancement exactly as before this dialog existed.
 *
 * The parent only mounts this component while the prompt is showing (see
 * dual-editor-field.tsx's `enhancePrompt` state), so `open` is always true here — the
 * Dialog unmounts along with this component when the parent stops rendering it. */
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
    <Dialog open onClose={onCancel} aria-label={actionLabel} className="ai-glow ai-glow--generating max-w-md">
      <div className="space-y-3 p-4">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-accent" />
          <h2 className="text-sm font-medium">{actionLabel}</h2>
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
            // Escape is handled by the native <dialog>'s own "cancel" event (see
            // components/ui/dialog.tsx) — no need to check for it here too.
          }}
          placeholder="e.g. My role was developing the model training pipeline and testing — update this based on that"
          rows={4}
          className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent"
        />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="button" size="sm" onClick={submit}>
            <Sparkles size={13} /> Enhance
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
