"use client";

import { useEffect, useRef, useState } from "react";
import { useShowProviderErrorModal } from "@/components/layout/provider-error-modal";
import { ApiError } from "@/lib/api-client";
import { streamChatTurn, type ChatMessage } from "@/lib/chat";
import type { ChatProvider } from "@/lib/types";

export type ToolStatus = {
  toolCallId: string;
  name: string;
  label: string;
  state: "running" | "done";
  result?: ChatMessage["tool_result"];
};

export type ChatDraft =
  | { status: "idle" }
  | { status: "streaming"; text: string; tools: ToolStatus[] }
  | { status: "error"; message: string };

/**
 * Deliberately does NOT reconstruct assistant/tool messages client-side from the SSE
 * stream — once a turn's `done` event fires, `onFinalize` (wired to refetch the message
 * history query) re-pulls the authoritative, already-persisted sequence from the server
 * (see backend chat_service._persist_turn) instead. The draft here only ever holds the
 * transient in-flight text + tool-status rows shown *while* streaming.
 */
export function useChatStream({
  sessionId,
  onUserMessage,
  onFinalize,
}: {
  sessionId: string | null;
  onUserMessage: (content: string, attachmentIds: string[]) => void;
  onFinalize: () => void;
}) {
  const [draft, setDraft] = useState<ChatDraft>({ status: "idle" });
  const abortRef = useRef<AbortController | null>(null);
  const showProviderError = useShowProviderErrorModal();

  // sessionId can now change while a stream is in flight (resuming a different
  // conversation from the Conversations page) — abort the old stream so it can't keep
  // rendering against a session this hook has moved past. Real subscription-cleanup
  // work, so this stays an effect (unlike the draft reset below).
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, [sessionId]);

  // Render-phase state adjustment (react.dev/learn/you-might-not-need-an-effect),
  // matching ConfirmPopover's prevOpen pattern, rather than a setState-in-effect.
  const [prevSessionId, setPrevSessionId] = useState(sessionId);
  if (prevSessionId !== sessionId) {
    setPrevSessionId(sessionId);
    setDraft({ status: "idle" });
  }

  const send = async (content: string, opts?: { attachmentIds?: string[]; provider?: ChatProvider }) => {
    const attachmentIds = opts?.attachmentIds ?? [];
    if (!sessionId || (!content.trim() && attachmentIds.length === 0)) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    onUserMessage(content, attachmentIds);
    setDraft({ status: "streaming", text: "", tools: [] });

    try {
      for await (const event of streamChatTurn({
        sessionId,
        content,
        provider: opts?.provider,
        attachmentIds,
        signal: controller.signal,
      })) {
        switch (event.type) {
          case "token":
            setDraft((prev) => (prev.status === "streaming" ? { ...prev, text: prev.text + event.delta } : prev));
            break;
          case "tool_start":
            setDraft((prev) =>
              prev.status === "streaming"
                ? {
                    ...prev,
                    tools: [
                      ...prev.tools,
                      { toolCallId: event.tool_call_id, name: event.name, label: event.label, state: "running" },
                    ],
                  }
                : prev,
            );
            break;
          case "tool_end":
            setDraft((prev) =>
              prev.status === "streaming"
                ? {
                    ...prev,
                    tools: prev.tools.map((t) =>
                      t.toolCallId === event.tool_call_id ? { ...t, state: "done", result: event.result } : t,
                    ),
                  }
                : prev,
            );
            break;
          case "error":
            if (!showProviderError({ code: event.code })) {
              setDraft({ status: "error", message: event.message });
            } else {
              setDraft({ status: "idle" });
            }
            return;
          case "done":
            setDraft({ status: "idle" });
            onFinalize();
            break;
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      if (err instanceof ApiError && showProviderError({ code: err.code, provider: err.provider })) {
        setDraft({ status: "idle" });
        return;
      }
      setDraft({ status: "error", message: err instanceof Error ? err.message : "Something went wrong" });
    }
  };

  /** Aborts the client-side fetch, but does NOT abort the server-side turn (it keeps
   * streaming/persisting in the background — see frontend/DESIGN.md's note on this) —
   * `onFinalize` still runs so the partially-persisted turn shows up once it lands. */
  const stop = () => {
    abortRef.current?.abort();
    setDraft({ status: "idle" });
    onFinalize();
  };

  const dismissError = () => setDraft({ status: "idle" });

  return { draft, send, stop, dismissError };
}
