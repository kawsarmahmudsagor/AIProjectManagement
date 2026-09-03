import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { TasksClient } from "@/components/tasks/tasks-client";
import { serverApiFetch } from "@/lib/server-api";
import type { Project, TaskListResponse } from "@/lib/types";

export default async function ProjectTasksPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;

  let project: Project;
  let tasks: TaskListResponse;
  try {
    [project, tasks] = await Promise.all([
      serverApiFetch<Project>(`projects/${projectId}`),
      serverApiFetch<TaskListResponse>(`projects/${projectId}/tasks?page_size=100`),
    ]);
  } catch {
    notFound();
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link
        href={`/projects/${projectId}`}
        className="mb-2 inline-flex items-center gap-1 text-sm text-muted hover:text-foreground"
      >
        <ArrowLeft size={14} /> {project.name}
      </Link>
      <h1 className="mb-6 text-2xl font-semibold">Tasks</h1>
      <TasksClient projectId={projectId} initialData={tasks} />
    </div>
  );
}
