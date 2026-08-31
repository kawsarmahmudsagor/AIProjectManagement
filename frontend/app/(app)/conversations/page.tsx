import { ConversationFilters } from "@/components/conversations/conversation-filters";
import { ConversationList } from "@/components/conversations/conversation-list";
import { ConversationSearch } from "@/components/conversations/conversation-search";
import type { ChatSessionListResponse } from "@/lib/chat";
import { serverApiFetch } from "@/lib/server-api";

export default async function ConversationsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; starred?: string; sort?: string }>;
}) {
  const { q, starred, sort } = await searchParams;
  let data: ChatSessionListResponse = { items: [], total: 0 };
  let loadError: string | null = null;
  try {
    const qs = new URLSearchParams({
      page: "1",
      page_size: "50",
      sort: sort === "asc" ? "asc" : "desc",
      ...(q ? { q } : {}),
      ...(starred === "true" ? { starred_only: "true" } : {}),
    });
    data = await serverApiFetch<ChatSessionListResponse>(`chat/sessions?${qs.toString()}`);
  } catch {
    loadError = "Couldn't reach the API — is the backend running?";
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Conversations</h1>
          <p className="text-sm text-muted">
            {data.total} conversation{data.total === 1 ? "" : "s"} with Jarvis
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ConversationSearch />
          <ConversationFilters />
        </div>
      </div>

      {loadError && <p className="text-sm text-danger">{loadError}</p>}

      {!loadError && <ConversationList sessions={data.items} />}
    </div>
  );
}
