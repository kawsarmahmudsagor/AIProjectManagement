"use client";

import { useRef, useState } from "react";
import { useShowProviderErrorModal } from "@/components/layout/provider-error-modal";
import { requestAiRewrite, type AiEnhanceOp, type AiRewriteContext, type ProjectSectionKey } from "@/lib/ai";
import { ApiError } from "@/lib/api-client";
import { countPlain } from "@/lib/rich-text/count";
import type { RichText } from "@/lib/rich-text/types";

export type SuggestionState =
  | { status: "idle" }
  | { status: "loading"; op: AiEnhanceOp }
  | { status: "ready"; op: AiEnhanceOp; suggestion: RichText; overLimit: boolean }
  | { status: "error"; op: AiEnhanceOp; message: string };

/**
 * Hard rule (DESIGN.md §4.4): an AI response is never written into an editor without an
 * explicit user action. This hook only ever produces a *suggestion* — `onAccept` (wired
 * to bumping the field's revision, see DualEditorField) is the only path that writes it
 * into the document, and only when the caller invokes `accept()`.
 */
export function useFieldSuggestion({
  section,
  limit,
  onAccept,
}: {
  section: ProjectSectionKey;
  limit: number;
  onAccept: (value: RichText) => void;
}) {
  const [state, setState] = useState<SuggestionState>({ status: "idle" });
  const showProviderError = useShowProviderErrorModal();
  const abortRef = useRef<AbortController | null>(null);
  const lastRunRef = useRef<{
    op: AiEnhanceOp;
    target: RichText;
    source: RichText;
    context?: AiRewriteContext;
    instruction?: string;
  } | null>(null);

  const run = async (
    op: AiEnhanceOp,
    target: RichText,
    source: RichText,
    context?: AiRewriteContext,
    instruction?: string,
  ) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    lastRunRef.current = { op, target, source, context, instruction };
    setState({ status: "loading", op });

    try {
      const suggestion = await requestAiRewrite({
        op,
        section,
        target,
        source,
        context,
        instruction,
        signal: controller.signal,
      });
      setState({ status: "ready", op, suggestion, overLimit: countPlain(suggestion.text) > limit });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setState({ status: "idle" });
        return;
      }
      if (err instanceof ApiError && showProviderError({ code: err.code, provider: err.provider })) {
        setState({ status: "idle" });
        return;
      }
      setState({ status: "error", op, message: err instanceof Error ? err.message : "Something went wrong" });
    }
  };

  const retry = () => {
    if (!lastRunRef.current) return;
    const { op, target, source, context, instruction } = lastRunRef.current;
    void run(op, target, source, context, instruction);
  };

  const accept = () => {
    if (state.status !== "ready") return;
    onAccept(state.suggestion);
    setState({ status: "idle" });
  };

  const discard = () => {
    abortRef.current?.abort();
    setState({ status: "idle" });
  };

  return { state, run, retry, accept, discard };
}
