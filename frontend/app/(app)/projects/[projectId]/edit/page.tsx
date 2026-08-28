import { notFound } from "next/navigation";
import { ProjectForm } from "@/components/projects/project-form";
import { serverApiFetch } from "@/lib/server-api";
import type { Project } from "@/lib/types";

export default async function EditProjectPage({
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
      <h1 className="mb-6 text-2xl font-semibold">Edit Project</h1>
      <ProjectForm project={project} />
    </div>
  );
}
