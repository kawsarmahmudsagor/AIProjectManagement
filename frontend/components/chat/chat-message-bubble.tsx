import { File, Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { RepoSuggestionCard } from "@/components/chat/repo-suggestion-card";
import { formatBytes } from "@/lib/chat-attachments";
import type { ChatMessage, RepoSuggestion } from "@/lib/chat";
import { mediaUrl } from "@/lib/media-url";
import type { ChatAttachment } from "@/lib/types";
import { cn } from "@/lib/utils";

function UserBubble({ content, attachments }: { content: string; attachments: ChatAttachment[] }) {
  const images = attachments.filter((a) => a.kind === "image");
  const documents = attachments.filter((a) => a.kind === "document");

  return (
    <div className="ml-auto max-w-[85%] space-y-2">
      {(images.length > 0 || documents.length > 0) && (
        <div className="ml-auto flex max-w-full flex-wrap justify-end gap-2">
          {images.map((a) => (
            <a key={a.id} href={mediaUrl(a.url)} target="_blank" rel="noreferrer">
              {/* eslint-disable-next-line @next/next/no-img-element -- user-uploaded, served from our own API */}
              <img src={mediaUrl(a.url)} alt={a.filename} className="h-20 w-20 rounded-md object-cover" />
            </a>
          ))}
          {documents.map((a) => (
            <a
              key={a.id}
              href={mediaUrl(a.url)}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 rounded-lg border border-border bg-surface-2 px-2.5 py-1.5 text-xs hover:bg-surface-3"
            >
              <File size={14} className="shrink-0 text-muted" />
              <span className="max-w-[140px] truncate">{a.filename}</span>
              <span className="shrink-0 text-muted">{formatBytes(a.size_bytes)}</span>
            </a>
          ))}
        </div>
      )}
      {content && (
        <div className="rounded-lg rounded-tr-sm bg-accent px-3 py-2 text-sm text-accent-foreground">{content}</div>
      )}
    </div>
  );
}

function AssistantBubble({ content }: { content: string }) {
  return (
    <div className="mr-auto max-w-[85%] rounded-lg rounded-tl-sm border border-border bg-surface px-3 py-2">
      <div className="prose prose-invert prose-sm max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    </div>
  );
}

// Roughly the height of 3 RepoSuggestionCards (each ~92px with a 2-line description
// and language tag, plus the 8px gap between them) — beyond that the list scrolls
// inside the card instead of growing it indefinitely.
const VISIBLE_REPO_COUNT = 3;

/** Visually distinct bordered/tinted container — same treatment as AiSuggestionPanel's
 * "ready" state — so GitHub suggestions read as AI-proposed content, not inline prose. */
function RepoSuggestionsBlock({ repos }: { repos: RepoSuggestion[] }) {
  return (
    <div className="mr-auto w-[85%] space-y-2 rounded-lg border border-accent/30 bg-accent/5 p-2">
      <p className="flex items-center gap-1.5 px-1 text-xs font-medium text-accent">
        <Sparkles size={12} /> Suggested repositories
      </p>
      <div
        className={cn(
          "space-y-2",
          repos.length > VISIBLE_REPO_COUNT && "max-h-[300px] overflow-y-auto pr-1",
        )}
      >
        {repos.map((repo) => (
          <RepoSuggestionCard key={repo.full_name} repo={repo} />
        ))}
      </div>
    </div>
  );
}

function extractRepos(message: ChatMessage): RepoSuggestion[] {
  return (message.tool_result as { repos?: RepoSuggestion[] } | null)?.repos ?? [];
}

/** One persisted ChatMessage row. Callers should already have filtered out rows this
 * component has nothing to show for (see chat-message-list.tsx's `isRenderable`). */
export function ChatMessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") return <UserBubble content={message.content} attachments={message.attachments} />;

  if (message.role === "assistant") return <AssistantBubble content={message.content} />;

  // role === "tool" — only github_search results with at least one repo are ever shown;
  // project_search/portfolio_analysis results are data for the LLM, not user-facing.
  return <RepoSuggestionsBlock repos={extractRepos(message)} />;
}

/** Whether a persisted row has anything to render at all — an assistant row that only
 * made tool calls has empty content (nothing to show; the tool_start/tool_end indicator
 * already covered it live, and isn't replayed on reload), and a tool row is only shown
 * when it's a github_search result with repos. A user row is always renderable, even
 * with empty text, once attachments exist (an attachment-only message). */
export function isRenderable(message: ChatMessage): boolean {
  if (message.role === "user") return true;
  if (message.role === "assistant") return message.content.trim().length > 0;
  return extractRepos(message).length > 0;
}

/** Whether this row is a github_search repo-suggestion card — chat-message-list.tsx
 * uses this to render such cards after the turn's reply text instead of before it (the
 * persisted row order reflects when the tool ran, which is before the model's final
 * reply references it). */
export function hasRepoSuggestions(message: ChatMessage): boolean {
  return message.role === "tool" && extractRepos(message).length > 0;
}
