import { Sparkles } from "lucide-react";
import { RepoSuggestionCard } from "@/components/chat/repo-suggestion-card";
import type { ChatMessage, RepoSuggestion } from "@/lib/chat";

function UserBubble({ content }: { content: string }) {
  return (
    <div className="ml-auto max-w-[85%] rounded-lg rounded-tr-sm bg-accent px-3 py-2 text-sm text-accent-foreground">
      {content}
    </div>
  );
}

function AssistantBubble({ content }: { content: string }) {
  return (
    <div className="mr-auto max-w-[85%] rounded-lg rounded-tl-sm border border-border bg-surface px-3 py-2 text-sm">
      {content}
    </div>
  );
}

/** Visually distinct bordered/tinted container — same treatment as AiSuggestionPanel's
 * "ready" state — so GitHub suggestions read as AI-proposed content, not inline prose. */
function RepoSuggestionsBlock({ repos }: { repos: RepoSuggestion[] }) {
  return (
    <div className="mr-auto w-[85%] space-y-2 rounded-lg border border-accent/30 bg-accent/5 p-2">
      <p className="flex items-center gap-1.5 px-1 text-xs font-medium text-accent">
        <Sparkles size={12} /> Suggested repositories
      </p>
      {repos.map((repo) => (
        <RepoSuggestionCard key={repo.full_name} repo={repo} />
      ))}
    </div>
  );
}

/** One persisted ChatMessage row. Callers should already have filtered out rows this
 * component has nothing to show for (see chat-message-list.tsx's `isRenderable`). */
export function ChatMessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") return <UserBubble content={message.content} />;

  if (message.role === "assistant") return <AssistantBubble content={message.content} />;

  // role === "tool" — only github_search results with at least one repo are ever shown;
  // project_search/portfolio_analysis results are data for the LLM, not user-facing.
  const repos = (message.tool_result as { repos?: RepoSuggestion[] } | null)?.repos ?? [];
  return <RepoSuggestionsBlock repos={repos} />;
}

/** Whether a persisted row has anything to render at all — an assistant row that only
 * made tool calls has empty content (nothing to show; the tool_start/tool_end indicator
 * already covered it live, and isn't replayed on reload), and a tool row is only shown
 * when it's a github_search result with repos. */
export function isRenderable(message: ChatMessage): boolean {
  if (message.role === "user") return true;
  if (message.role === "assistant") return message.content.trim().length > 0;
  const repos = (message.tool_result as { repos?: RepoSuggestion[] } | null)?.repos;
  return Boolean(repos && repos.length > 0);
}
