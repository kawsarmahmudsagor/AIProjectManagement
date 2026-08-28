import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ProjectCard } from "@/components/projects/project-card";
import { serverApiFetch } from "@/lib/server-api";
import type { ProjectListResponse } from "@/lib/types";

export default async function DashboardPage() {
  let data: ProjectListResponse = { items: [], total: 0 };
  let loadError: string | null = null;
  try {
    data = await serverApiFetch<ProjectListResponse>("projects?page=1&page_size=12");
  } catch {
    loadError = "Couldn't reach the API — is the backend running?";
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-muted">{data.total} project{data.total === 1 ? "" : "s"}</p>
        </div>
        <Link href="/projects/new">
          <Button>Add New Project</Button>
        </Link>
      </div>

      {loadError && <p className="text-sm text-danger">{loadError}</p>}

      {!loadError && data.items.length === 0 && (
        <p className="text-sm text-muted">
          No projects yet. <Link href="/projects/new" className="text-accent hover:underline">Add your first one</Link>.
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.items.map((project) => (
          <ProjectCard key={project.id} project={project} />
        ))}
      </div>
    </div>
  );
}
