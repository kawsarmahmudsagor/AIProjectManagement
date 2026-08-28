"use client";

import { useController, type Control, type FieldPath, type FieldValues } from "react-hook-form";
import { RichTextEditor, type AiGlowState } from "@/components/editor/rich-text-editor";
import type { ToolbarAiAction } from "@/components/editor/editor-toolbar";
import { useDebouncedCallback } from "@/hooks/use-debounced-callback";
import type { RichText } from "@/lib/rich-text/types";

/**
 * The RHF <-> Tiptap seam (DESIGN.md §1c). Tiptap owns the document between external
 * writes; `field.onChange` fires on a debounce (+ immediately on blur) so RHF state
 * churns a few times a second at most, not on every keystroke. `revision` is supplied by
 * the parent (DualEditorField) and must only change on external writes (AI accept,
 * revert, form reset) — never as a side effect of typing.
 */
export function RichTextField<TFieldValues extends FieldValues>({
  control,
  name,
  limit,
  placeholder,
  revision,
  disabled,
  ariaLabel,
  aiActions,
  aiGlow,
}: {
  control: Control<TFieldValues>;
  name: FieldPath<TFieldValues>;
  limit: number;
  placeholder: string;
  revision: number;
  disabled?: boolean;
  ariaLabel?: string;
  aiActions?: ToolbarAiAction[];
  aiGlow?: AiGlowState;
}) {
  const { field } = useController({ control, name });
  const value = (field.value ?? { html: "", text: "" }) as RichText;

  const { run: commit, flush } = useDebouncedCallback((v: RichText) => field.onChange(v), 250);

  return (
    <RichTextEditor
      externalValue={value}
      externalRevision={revision}
      limit={limit}
      placeholder={placeholder}
      disabled={disabled}
      aria-label={ariaLabel}
      aiActions={aiActions}
      aiGlow={aiGlow}
      onChange={commit}
      onBlur={() => {
        flush();
        field.onBlur();
      }}
    />
  );
}
