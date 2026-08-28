"use client";

import { useRef, useState } from "react";
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
  onUserMessage: (content: string) => void;
  onFinalize: () => void;
}) {
  const [draft, setDraft] = useState<ChatDraft>({ status: "idle" });
  const abortRef = useRef<AbortController | null>(null);
  const showProviderError = useShowProviderErrorModal();

  const send = async (content: string, provider?: ChatProvider) => {
    if (!sessionId || !content.trim()) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    onUserMessage(content);
    setDraft({ status: "streaming", text: "", tools: [] });

    try {
      for await (const event of streamChatTurn({ sessionId, content, provider, signal: controller.signal })) {
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

  const dismissError = () => setDraft({ status: "idle" });

  return { draft, send, dismissError };
}
