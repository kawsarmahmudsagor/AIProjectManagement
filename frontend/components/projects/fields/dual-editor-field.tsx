"use client";

import { useEffect, useRef, useState } from "react";
import { useWatch, type Control, type FieldPath, type FieldValues, type UseFormGetValues, type UseFormSetValue } from "react-hook-form";
import { RichTextField } from "@/components/editor/rich-text-field";
import type { AiGlowState } from "@/components/editor/rich-text-editor";
import type { ToolbarAiAction } from "@/components/editor/editor-toolbar";
import { AiEnhanceContextDialog } from "@/components/projects/ai/ai-enhance-context-dialog";
import { AiSuggestionPanel } from "@/components/projects/ai/ai-suggestion-panel";
import { Badge } from "@/components/ui/card";
import { useFieldSuggestion } from "@/hooks/use-field-suggestion";
import type { AiEnhanceOp, AiRewriteContext, ProjectSectionKey } from "@/lib/ai";
import { EMPTY_RICH_TEXT, type RichText } from "@/lib/rich-text/types";

interface EditorBlockConfig<TFieldValues extends FieldValues> {
  name: FieldPath<TFieldValues>;
  label: string;
  badge: string;
  limit: number;
  placeholder: string;
  tooltip: string;
}

export interface DualEditorFieldProps<TFieldValues extends FieldValues> {
  section: ProjectSectionKey;
  title: string;
  helperText: string;
  control: Control<TFieldValues>;
  getValues: UseFormGetValues<TFieldValues>;
  setValue: UseFormSetValue<TFieldValues>;
  /** Surrounding project fields (name, role, technologies) so a rewrite reads naturally
   * next to the rest of the entry — read fresh at request time, not on every render. */
  buildContext?: () => AiRewriteContext;
  long: EditorBlockConfig<TFieldValues> & { enhanceLabel: string };
  short: EditorBlockConfig<TFieldValues> & {
    requirement: "required" | "recommended";
    generateLabel: string;
    enhanceLabel: string;
    errorMessage?: string;
  };
  disabled?: boolean;
  /** An external write (e.g. document-extraction autofill) rather than a per-field AI
   * suggestion accept. `token` must be bumped by the caller for each new payload — the
   * editors only re-sync on a token change, same revision protocol as the suggestion
   * accept path. The caller is responsible for deciding *which* fields are safe to
   * overwrite (e.g. skipping ones the user already edited) before setting this. */
  autofill?: { token: number; long?: RichText; short?: RichText };
}

/** How long the "applied" glow pulse plays after an AI suggestion is accepted into a
 * box — long enough to notice, short enough to not linger and read as "still AI's". */
const APPLIED_GLOW_MS = 1600;

function useAppliedPulse(): [boolean, () => void] {
  const [applied, setApplied] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => clearTimeout(timeoutRef.current), []);

  const trigger = () => {
    setApplied(true);
    clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setApplied(false), APPLIED_GLOW_MS);
  };

  return [applied, trigger];
}

export function DualEditorField<TFieldValues extends FieldValues>({
  section,
  title,
  helperText,
  control,
  getValues,
  setValue,
  buildContext,
  long,
  short,
  disabled,
  autofill,
}: DualEditorFieldProps<TFieldValues>) {
  const [longRevision, setLongRevision] = useState(0);
  const [shortRevision, setShortRevision] = useState(0);
  const [longApplied, pulseLongApplied] = useAppliedPulse();
  const [shortApplied, pulseShortApplied] = useAppliedPulse();
  // Which box's "Enhance" button opened the context prompt, if any — "Generate from long"
  // is unaffected and still runs immediately, this only gates the two enhance-* ops.
  const [enhancePrompt, setEnhancePrompt] = useState<{ box: "long" | "short"; label: string } | null>(null);

  // NOT done in the render body: `setValue` belongs to the parent's `useForm()` instance
  // (ProjectForm), not to this component, so calling it while DualEditorField itself is
  // rendering is exactly the case React warns about ("Cannot update a component while
  // rendering a different component") — the write does not reliably reach the parent's
  // form state from there. An Effect keyed on the autofill token is the correct place for
  // it; the one-render delay this adds only affects a one-time external autofill, never
  // typing (typing never changes `autofill`).
  const appliedAutofillTokenRef = useRef(autofill?.token ?? 0);
  useEffect(() => {
    if (!autofill || autofill.token === appliedAutofillTokenRef.current) return;
    appliedAutofillTokenRef.current = autofill.token;
    if (autofill.long) {
      setValue(long.name, autofill.long as never, { shouldDirty: true, shouldValidate: true });
      setLongRevision((r) => r + 1);
      pulseLongApplied();
    }
    if (autofill.short) {
      setValue(short.name, autofill.short as never, { shouldDirty: true, shouldValidate: true });
      setShortRevision((r) => r + 1);
      pulseShortApplied();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autofill]);

  const readValue = (name: FieldPath<TFieldValues>): RichText =>
    (getValues(name) as RichText | undefined) ?? EMPTY_RICH_TEXT;

  const longSuggestion = useFieldSuggestion({
    section,
    limit: long.limit,
    onAccept: (value) => {
      setValue(long.name, value as never, { shouldDirty: true, shouldValidate: true });
      setLongRevision((r) => r + 1);
      pulseLongApplied();
    },
  });

  const shortSuggestion = useFieldSuggestion({
    section,
    limit: short.limit,
    onAccept: (value) => {
      setValue(short.name, value as never, { shouldDirty: true, shouldValidate: true });
      setShortRevision((r) => r + 1);
      pulseShortApplied();
    },
  });

  // Reactive (unlike getValues) so the AI button disabled state tracks typing — this
  // re-renders DualEditorField on the ~250ms debounce, not on every keystroke, and never
  // touches the RichTextEditor's own props identity that would reset its content (the
  // editor instance only re-reads `externalValue` when `revision` changes, see
  // rich-text-editor.tsx).
  const longWatched = useWatch({ control, name: long.name }) as RichText | undefined;
  const shortWatched = useWatch({ control, name: short.name }) as RichText | undefined;
  const isLongEmpty = (longWatched?.text ?? "").trim().length === 0;
  const isShortEmpty = (shortWatched?.text ?? "").trim().length === 0;

  const runLong = (op: AiEnhanceOp, instruction?: string) =>
    longSuggestion.run(op, readValue(long.name), readValue(long.name), buildContext?.(), instruction);
  const runShort = (op: AiEnhanceOp, instruction?: string) =>
    shortSuggestion.run(
      op,
      readValue(short.name),
      op === "generate-short" ? readValue(long.name) : readValue(short.name),
      buildContext?.(),
      instruction,
    );

  const submitEnhancePrompt = (instruction?: string) => {
    if (enhancePrompt?.box === "long") runLong("enhance-long", instruction);
    else if (enhancePrompt?.box === "short") runShort("enhance-short", instruction);
    setEnhancePrompt(null);
  };

  const longGlow: AiGlowState = longSuggestion.state.status === "loading" ? "generating" : longApplied ? "applied" : "idle";
  const shortGlow: AiGlowState = shortSuggestion.state.status === "loading" ? "generating" : shortApplied ? "applied" : "idle";

  const longAiActions: ToolbarAiAction[] = [
    {
      key: "enhance-long",
      label: long.enhanceLabel,
      icon: "sparkles",
      disabled: disabled || isLongEmpty,
      loading: longSuggestion.state.status === "loading",
      onClick: () => setEnhancePrompt({ box: "long", label: long.enhanceLabel }),
    },
  ];

  const shortAiActions: ToolbarAiAction[] = [
    {
      key: "generate-short",
      label: short.generateLabel,
      icon: "wand",
      disabled: disabled || isLongEmpty,
      loading: shortSuggestion.state.status === "loading" && shortSuggestion.state.op === "generate-short",
      onClick: () => runShort("generate-short"),
    },
    {
      key: "enhance-short",
      label: short.enhanceLabel,
      icon: "sparkles",
      disabled: disabled || isShortEmpty,
      loading: shortSuggestion.state.status === "loading" && shortSuggestion.state.op === "enhance-short",
      onClick: () => setEnhancePrompt({ box: "short", label: short.enhanceLabel }),
    },
  ];

  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-medium">{title}</h2>
        <p className="text-sm text-muted">{helperText}</p>
      </div>

      <div>
        <div className="mb-1.5 flex items-center gap-2">
          <label className="text-sm font-medium" title={long.tooltip}>
            {long.label}
          </label>
          <Badge>{long.badge}</Badge>
        </div>
        <RichTextField
          control={control}
          name={long.name}
          limit={long.limit}
          placeholder={long.placeholder}
          revision={longRevision}
          disabled={disabled}
          ariaLabel={long.label}
          aiActions={longAiActions}
          aiGlow={longGlow}
        />
        <AiSuggestionPanel
          state={longSuggestion.state}
          limit={long.limit}
          onAccept={longSuggestion.accept}
          onRetry={longSuggestion.retry}
          onDiscard={longSuggestion.discard}
        />
      </div>

      <div>
        <div className="mb-1.5 flex items-center gap-2">
          <label className="text-sm font-medium" title={short.tooltip}>
            {short.label}
          </label>
          <Badge className={short.requirement === "required" ? "bg-accent/15 text-accent" : undefined}>
            {short.requirement === "required" ? "Required" : "Recommended"}
          </Badge>
        </div>
        <RichTextField
          control={control}
          name={short.name}
          limit={short.limit}
          placeholder={short.placeholder}
          revision={shortRevision}
          disabled={disabled}
          ariaLabel={short.label}
          aiActions={shortAiActions}
          aiGlow={shortGlow}
        />
        {short.errorMessage && <p className="mt-1 text-xs text-danger">{short.errorMessage}</p>}
        <AiSuggestionPanel
          state={shortSuggestion.state}
          limit={short.limit}
          onAccept={shortSuggestion.accept}
          onRetry={shortSuggestion.retry}
          onDiscard={shortSuggestion.discard}
        />
      </div>

      {enhancePrompt && (
        <AiEnhanceContextDialog
          actionLabel={enhancePrompt.label}
          onCancel={() => setEnhancePrompt(null)}
          onSubmit={submitEnhancePrompt}
        />
      )}
    </div>
  );
}
