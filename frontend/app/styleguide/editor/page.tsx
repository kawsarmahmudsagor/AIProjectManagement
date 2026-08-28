"use client";

/**
 * Standalone exercise page for the rich-text editor, matching DESIGN.md §9 M3's
 * acceptance criteria — the page itself is reachable without auth (see proxy.ts), so
 * toolbar layout, char-cap enforcement, and paste truncation can all be checked with no
 * backend running. The DualEditorField demo below still calls the real /api/bff/ai/rewrite
 * endpoint (DualEditorField has no mock injection seam — it isn't needed by the real app),
 * so without a running, authenticated backend the "Enhance"/"Generate from long" buttons
 * will flash the generating glow, then show the AiSuggestionPanel's error state — which is
 * itself a fine way to eyeball the loading/glow/error states even offline.
 */

import { useForm } from "react-hook-form";
import { RichTextEditor } from "@/components/editor/rich-text-editor";
import { DualEditorField } from "@/components/projects/fields/dual-editor-field";
import { useState } from "react";
import { EMPTY_RICH_TEXT, type RichText } from "@/lib/rich-text/types";

function StandaloneEditor({ limit, label }: { limit: number; label: string }) {
  const [value, setValue] = useState<RichText>(EMPTY_RICH_TEXT);
  const [revision] = useState(0);

  return (
    <div>
      <h3 className="mb-2 text-sm font-medium text-muted">{label}</h3>
      <RichTextEditor
        externalValue={value}
        externalRevision={revision}
        limit={limit}
        placeholder={`Type here — capped at ${limit.toLocaleString()} characters...`}
        onChange={setValue}
      />
    </div>
  );
}

function DualEditorDemo() {
  const form = useForm({
    defaultValues: {
      description: { long: EMPTY_RICH_TEXT, short: EMPTY_RICH_TEXT },
    },
  });

  return (
    <div>
      <h3 className="mb-2 text-sm font-medium text-muted">
        DualEditorField (calls the real /api/bff/ai/rewrite — needs a logged-in session and a running backend to succeed)
      </h3>
      <DualEditorField
        section="description"
        title="Project Description"
        helperText="Fill the long form first for full detail, then generate a short summary from it."
        control={form.control}
        getValues={form.getValues}
        setValue={form.setValue}
        long={{
          name: "description.long",
          label: "Long form",
          badge: "Optional · up to 10,000 chars",
          limit: 10_000,
          placeholder: "Write the full, detailed project description here...",
          tooltip: "Source for the short summary.",
          enhanceLabel: "Enhance long with AI",
        }}
        short={{
          name: "description.short",
          label: "Short summary",
          badge: "Required",
          requirement: "required",
          limit: 390,
          placeholder: "Concise summary used in compact views",
          tooltip: "Under 390 characters.",
          generateLabel: "Generate from long",
          enhanceLabel: "Enhance",
        }}
      />
    </div>
  );
}

export default function EditorStyleguidePage() {
  return (
    <div className="mx-auto max-w-3xl space-y-10 p-8">
      <div>
        <h1 className="text-2xl font-semibold">Editor styleguide</h1>
        <p className="text-sm text-muted">
          Dev-only page, reachable without login (see proxy.ts). Exercises the Tiptap
          editor in isolation per frontend/DESIGN.md §9 milestone M3.
        </p>
      </div>

      <StandaloneEditor limit={390} label="390-char limit (try typing/pasting past it)" />
      <StandaloneEditor limit={10_000} label="10,000-char limit" />
      <DualEditorDemo />
    </div>
  );
}
