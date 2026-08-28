"use client";

import { EditorContent, useEditor, useEditorState } from "@tiptap/react";
import { useEffect, useRef } from "react";
import { EditorToolbar, type ToolbarAiAction } from "@/components/editor/editor-toolbar";
import { buildExtensions } from "@/components/editor/editor-extensions";
import { countPlain } from "@/lib/rich-text/count";
import { cn } from "@/lib/utils";
import type { RichText } from "@/lib/rich-text/types";

export type AiGlowState = "idle" | "generating" | "applied";

export interface RichTextEditorProps {
  /** Current value. Only re-applied to the editor when `externalRevision` changes (see
   * the revision protocol below) — never on every keystroke, which would fight typing
   * and destroy undo history (DESIGN.md §1a/§1c). */
  externalValue: RichText;
  /** Bump this only on external writes: AI accept, revert, form reset. Typing inside this
   * editor must never change it. */
  externalRevision: number;
  limit: number;
  placeholder: string;
  onChange: (value: RichText) => void;
  onBlur?: () => void;
  disabled?: boolean;
  className?: string;
  "aria-label"?: string;
  /** Icon buttons rendered in the toolbar's top-right corner (e.g. "Enhance with AI"). */
  aiActions?: ToolbarAiAction[];
  /** Drives the Gemini-style animated gradient ring: "generating" while a request for
   * this box is in flight, "applied" for a brief pulse right after a suggestion is
   * accepted into it. */
  aiGlow?: AiGlowState;
}

export function RichTextEditor({
  externalValue,
  externalRevision,
  limit,
  placeholder,
  onChange,
  onBlur,
  disabled,
  className,
  "aria-label": ariaLabel,
  aiActions,
  aiGlow = "idle",
}: RichTextEditorProps) {
  const appliedRevision = useRef(externalRevision);
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  });

  // Tiptap normalizes an empty/invalid initial `content` (e.g. "") into a valid empty
  // doc as part of creating the editor, and that normalization fires `onUpdate` once,
  // before any real keystroke. Left unguarded, that phantom update flows through
  // `onChange` into RHF's `field.onChange` and permanently marks the field dirty from
  // page load — which then blocks the document-extraction autofill's "never overwrite a
  // field the user already touched" check (project-form.tsx's `dirtyFields` guard) even
  // though the user never touched it. Skip exactly that first call; every real update
  // after it (typing, paste) still fires `onChange` normally.
  const skipNextUpdateRef = useRef(true);

  const editor = useEditor({
    extensions: buildExtensions({ limit, placeholder }),
    content: externalValue.html,
    editable: !disabled,
    editorProps: {
      attributes: { class: "tiptap-content", ...(ariaLabel ? { "aria-label": ariaLabel } : {}) },
      // Guards against a known Tiptap bug where pasting content that overshoots the
      // character limit can blank the editor entirely (ueberdosis/tiptap#4820). If the
      // pasted plain text alone would exceed the remaining budget, we insert a truncated
      // plain-text fallback ourselves instead of letting the default (rich) paste run.
      handlePaste: (view, event) => {
        const text = event.clipboardData?.getData("text/plain");
        if (!text) return false;

        // Chars that will remain once the current selection is replaced by the paste.
        const fullText = view.state.doc.textBetween(0, view.state.doc.content.size, "\n");
        const selectedText = view.state.doc.textBetween(view.state.selection.from, view.state.selection.to, "\n");
        const remaining = limit - (countPlain(fullText) - countPlain(selectedText));

        if (countPlain(text) <= remaining) return false; // fits — let the default (rich) paste run

        event.preventDefault();
        const truncated = [...text].slice(0, Math.max(remaining, 0)).join("");
        view.dispatch(view.state.tr.insertText(truncated, view.state.selection.from, view.state.selection.to));
        return true;
      },
    },
    onUpdate: ({ editor: e }) => {
      if (skipNextUpdateRef.current) {
        skipNextUpdateRef.current = false;
        return;
      }
      onChangeRef.current({ html: e.getHTML(), text: e.getText({ blockSeparator: "\n" }) });
    },
    onBlur: () => onBlur?.(),
    immediatelyRender: false,
  });

  useEffect(() => {
    if (!editor || appliedRevision.current === externalRevision) return;
    appliedRevision.current = externalRevision;
    editor.commands.setContent(externalValue.html, { emitUpdate: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor, externalRevision]);

  useEffect(() => {
    editor?.setEditable(!disabled);
  }, [editor, disabled]);

  const chars =
    useEditorState({
      editor,
      selector: ({ editor: e }) => e?.storage.characterCount.characters() ?? 0,
    }) ?? 0;

  const overLimit = chars >= limit;

  if (!editor) {
    return <div className={cn("h-32 animate-pulse rounded-lg border border-border bg-surface-2/40", className)} />;
  }

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-background",
        aiGlow === "generating" && "ai-glow ai-glow--generating",
        aiGlow === "applied" && "ai-glow ai-glow--applied",
        className,
      )}
    >
      <EditorToolbar editor={editor} aiActions={aiActions} />
      <EditorContent editor={editor} className="min-h-24 px-3 py-2 text-sm [&_.tiptap-content]:outline-none" />
      <div className="flex justify-end border-t border-border px-3 py-1">
        <span className={cn("text-xs tabular-nums", overLimit ? "text-danger" : "text-muted")}>
          {chars}/{limit}
        </span>
      </div>
    </div>
  );
}
