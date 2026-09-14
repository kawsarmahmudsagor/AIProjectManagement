import Link from "next/link";
import { AppSearch } from "@/components/dashboard/app-search";
import { ProjectListCompact } from "@/components/dashboard/project-list-compact";
import { RecentConversationsCard } from "@/components/dashboard/recent-conversations-card";
import { SkillsSummaryCard } from "@/components/dashboard/skills-summary-card";
import { SuggestedReposCard } from "@/components/dashboard/suggested-repos-card";
import { Button } from "@/components/ui/button";
import type { ChatSessionListResponse } from "@/lib/chat";
import { serverApiFetch } from "@/lib/server-api";
import type { GithubSuggestion } from "@/lib/suggestions";
import type { DashboardSummary } from "@/lib/types";

export default async function DashboardPage() {
  let summary: DashboardSummary = {
    total_projects: 0,
    current_projects: 0,
    technologies: [],
    distinct_technology_count: 0,
    primary_skills: [],
    secondary_skills: [],
    projects: [],
  };
  let loadError: string | null = null;
  try {
    summary = await serverApiFetch<DashboardSummary>("dashboard/summary");
  } catch {
    loadError = "Couldn't reach the API — is the backend running?";
  }

  // Same per-section try/catch convention as the summary fetch above — one dead
  // endpoint must never blank the whole dashboard.
  let chatData: ChatSessionListResponse = { items: [], total: 0 };
  try {
    chatData = await serverApiFetch<ChatSessionListResponse>("chat/sessions?page=1&page_size=5&sort=desc");
  } catch {
    // The Conversations card just renders empty — chat being down shouldn't fail the dashboard.
  }

  let suggestions: GithubSuggestion[] = [];
  try {
    suggestions = await serverApiFetch<GithubSuggestion[]>("suggestions/github");
  } catch {
    // Same reasoning as the Conversations card — the Suggested for you card just renders empty.
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-muted">
            {summary.total_projects} project{summary.total_projects === 1 ? "" : "s"}
          </p>
        </div>
        <Link href="/projects/new">
          <Button>Add New Project</Button>
        </Link>
      </div>

      {loadError && <p className="mb-4 text-sm text-danger">{loadError}</p>}

      <div className="mb-6">
        <AppSearch />
      </div>

      <div className="mb-6">
        <SkillsSummaryCard technologies={summary.technologies} />
      </div>

      <div className="grid grid-cols-1 gap-4 @4xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <ProjectListCompact projects={summary.projects} total={summary.total_projects} />
        <div className="space-y-4">
          <RecentConversationsCard sessions={chatData.items} />
          <SuggestedReposCard initialSuggestions={suggestions} />
        </div>
      </div>
    </div>
  );
}
