import { ConversationFilters } from "@/components/conversations/conversation-filters";
import { ConversationList } from "@/components/conversations/conversation-list";
import { ConversationSearch } from "@/components/conversations/conversation-search";
import { ConversationsTabs } from "@/components/conversations/conversations-tabs";
import { SuggestionsSection } from "@/components/conversations/suggestions-section";
import type { ChatSessionListResponse } from "@/lib/chat";
import type { GithubSuggestion } from "@/lib/suggestions";
import { serverApiFetch } from "@/lib/server-api";

export default async function ConversationsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; starred?: string; sort?: string; tab?: string }>;
}) {
  const { q, starred, sort, tab } = await searchParams;
  const showSuggestions = tab === "suggestions";

  let loadError: string | null = null;

  let data: ChatSessionListResponse = { items: [], total: 0 };
  let suggestions: GithubSuggestion[] = [];

  try {
    if (showSuggestions) {
      suggestions = await serverApiFetch<GithubSuggestion[]>("suggestions/github?scope=all");
    } else {
      const qs = new URLSearchParams({
        page: "1",
        page_size: "50",
        sort: sort === "asc" ? "asc" : "desc",
        ...(q ? { q } : {}),
        ...(starred === "true" ? { starred_only: "true" } : {}),
      });
      data = await serverApiFetch<ChatSessionListResponse>(`chat/sessions?${qs.toString()}`);
    }
  } catch {
    loadError = "Couldn't reach the API — is the backend running?";
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Conversations</h1>
          <p className="text-sm text-muted">
            {showSuggestions
              ? `${suggestions.length} suggestion${suggestions.length === 1 ? "" : "s"} from Jarvis`
              : `${data.total} conversation${data.total === 1 ? "" : "s"} with Jarvis`}
          </p>
        </div>
        {!showSuggestions && (
          <div className="flex items-center gap-3">
            <ConversationSearch />
            <ConversationFilters />
          </div>
        )}
      </div>

      <div className="mb-6">
        <ConversationsTabs />
      </div>

      {loadError && <p className="text-sm text-danger">{loadError}</p>}

      {!loadError && !showSuggestions && <ConversationList sessions={data.items} />}
      {!loadError && showSuggestions && <SuggestionsSection initialSuggestions={suggestions} />}
    </div>
  );
}
