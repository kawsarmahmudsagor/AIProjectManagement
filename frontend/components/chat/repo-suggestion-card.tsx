import { Star } from "lucide-react";
import type { RepoSuggestion } from "@/lib/chat";

/** Link-out only — no "insert"/"apply" action exists, which is what satisfies the
 * "AI proposes, never silently applies" rule here: there's nothing to apply a repo
 * suggestion *into* (frontend/DESIGN.md §4.4's equivalent for chat). */
export function RepoSuggestionCard({ repo }: { repo: RepoSuggestion }) {
  return (
    <a
      href={repo.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block rounded-lg border border-border bg-surface px-3 py-2 transition-colors hover:border-accent/40"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-sm font-medium">{repo.full_name}</span>
        <span className="flex shrink-0 items-center gap-1 text-xs text-muted">
          <Star size={12} className="fill-current" />
          {repo.stars.toLocaleString()}
        </span>
      </div>
      {repo.description && <p className="mt-1 line-clamp-2 text-xs text-muted">{repo.description}</p>}
      {repo.language && <span className="mt-1 inline-block text-xs text-muted">{repo.language}</span>}
    </a>
  );
}
