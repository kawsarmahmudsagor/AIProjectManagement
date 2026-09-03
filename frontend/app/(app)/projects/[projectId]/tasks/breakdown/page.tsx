import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { BreakdownClient } from "@/components/breakdown/breakdown-client";
import { serverApiFetch } from "@/lib/server-api";
import type { Project } from "@/lib/types";

export default async function ProjectBreakdownPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;

  let project: Project;
  try {
    project = await serverApiFetch<Project>(`projects/${projectId}`);
  } catch {
    notFound();
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link
        href={`/projects/${projectId}/tasks`}
        className="mb-2 inline-flex items-center gap-1 text-sm text-muted hover:text-foreground"
      >
        <ArrowLeft size={14} /> Tasks
      </Link>
      <h1 className="mb-1 text-2xl font-semibold">Break down {project.name}</h1>
      <p className="mb-6 text-sm text-muted">
        Upload a spec or describe the work — review every proposed task before anything is created.
      </p>
      {/* useSearchParams (for ?job=) requires a Suspense boundary around its nearest client usage. */}
      <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}>
        <BreakdownClient projectId={projectId} />
      </Suspense>
    </div>
  );
}
