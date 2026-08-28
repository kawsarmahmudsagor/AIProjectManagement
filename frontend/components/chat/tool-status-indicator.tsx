import { Check, Sparkles } from "lucide-react";
import type { ToolStatus } from "@/hooks/use-chat-stream";

/** Reuses the same `ai-glow`/Sparkles treatment as AiSuggestionPanel's loading state
 * (components/projects/ai/ai-suggestion-panel.tsx) rather than inventing new CSS. */
export function ToolStatusIndicator({ tool }: { tool: ToolStatus }) {
  return (
    <div
      className={
        tool.state === "running"
          ? "ai-glow ai-glow--generating flex items-center gap-2 rounded-lg border border-accent/30 bg-accent/5 px-3 py-1.5 text-xs text-muted"
          : "flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-muted"
      }
    >
      {tool.state === "running" ? (
        <Sparkles size={13} className="animate-pulse text-accent" />
      ) : (
        <Check size={13} className="text-accent" />
      )}
      {tool.label}
    </div>
  );
}
