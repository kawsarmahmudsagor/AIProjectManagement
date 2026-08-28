import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ProjectCard } from "@/components/projects/project-card";
import { ProjectSearch } from "@/components/projects/project-search";
import { serverApiFetch } from "@/lib/server-api";
import type { ProjectListResponse } from "@/lib/types";

export default async function ProjectsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  let data: ProjectListResponse = { items: [], total: 0 };
  let loadError: string | null = null;
  try {
    const qs = new URLSearchParams({ page: "1", page_size: "50", ...(q ? { q } : {}) });
    data = await serverApiFetch<ProjectListResponse>(`projects?${qs.toString()}`);
  } catch {
    loadError = "Couldn't reach the API — is the backend running?";
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Projects</h1>
        <div className="flex items-center gap-3">
          <ProjectSearch />
          <Link href="/projects/new">
            <Button>Add New Project</Button>
          </Link>
        </div>
      </div>

      {loadError && <p className="text-sm text-danger">{loadError}</p>}

      {!loadError && data.items.length === 0 && (
        <p className="text-sm text-muted">No projects match your search.</p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.items.map((project) => (
          <ProjectCard key={project.id} project={project} />
        ))}
      </div>
    </div>
  );
}
