import { Download, FileText, Pencil, ListChecks } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, Badge } from "@/components/ui/card";
import { DeleteProjectButton } from "@/components/projects/delete-project-button";
import { VideoFrameCarousel } from "@/components/projects/video-frame-carousel";
import { formatLongMonthYear as formatDate } from "@/lib/dates";
import { serverApiFetch } from "@/lib/server-api";
import type { Project, TaskListResponse } from "@/lib/types";

export default async function ProjectDetailPage({
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

  // Best-effort — a failed task count must never break the rest of the page, matching
  // the dashboard's per-section try/catch convention.
  let taskSummary = "";
  try {
    const tasks = await serverApiFetch<TaskListResponse>(
      `projects/${projectId}/tasks?page_size=1`,
    );
    const done = await serverApiFetch<TaskListResponse>(
      `projects/${projectId}/tasks?status=done&page_size=1`,
    );
    if (tasks.total > 0) taskSummary = `${done.total}/${tasks.total} done`;
  } catch {
    // silent — the Tasks link still works even if the count doesn't load
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{project.name}</h1>
          <p className="text-muted">{project.role}</p>
          <p className="mt-1 text-sm text-muted">
            {formatDate(project.start_date)} – {project.is_current ? "Present" : project.end_date ? formatDate(project.end_date) : ""}
          </p>
        </div>
        <div className="flex gap-2">
          <Link href={`/projects/${project.id}/tasks`}>
            <Button variant="secondary">
              <ListChecks size={14} /> Tasks{taskSummary && ` · ${taskSummary}`}
            </Button>
          </Link>
          <Link href={`/projects/${project.id}/edit`}>
            <Button variant="secondary">
              <Pencil size={14} /> Edit
            </Button>
          </Link>
          <a href={`/api/bff/projects/${project.id}/export?format=pdf`} target="_blank" rel="noreferrer">
            <Button variant="secondary">
              <FileText size={14} /> PDF
            </Button>
          </a>
          <a href={`/api/bff/projects/${project.id}/export?format=docx`} target="_blank" rel="noreferrer">
            <Button variant="secondary">
              <Download size={14} /> DOCX
            </Button>
          </a>
          <DeleteProjectButton projectId={project.id} projectName={project.name} redirectTo="/projects" />
        </div>
      </div>

      {project.project_url && (
        <a href={project.project_url} className="text-sm text-accent hover:underline">
          {project.project_url}
        </a>
      )}

      {project.video_frames.length > 0 && (
        <div className="mt-6">
          <VideoFrameCarousel frames={project.video_frames} />
        </div>
      )}

      {(project.description.long.html || project.description.short.html) && (
        <Card className="mt-6">
          <h2 className="mb-2 font-medium">Project Description</h2>
          <div
            className="prose prose-invert prose-sm max-w-none"
            dangerouslySetInnerHTML={{
              __html: project.description.long.html || project.description.short.html,
            }}
          />
        </Card>
      )}

      {(project.responsibilities.long.html || project.responsibilities.short.html) && (
        <Card className="mt-6">
          <h2 className="mb-2 font-medium">Responsibilities</h2>
          <div
            className="prose prose-invert prose-sm max-w-none"
            dangerouslySetInnerHTML={{
              __html: project.responsibilities.long.html || project.responsibilities.short.html,
            }}
          />
        </Card>
      )}

      {project.technologies.length > 0 && (
        <div className="mt-6 flex flex-wrap gap-2">
          {project.technologies.map((t) => (
            <Badge key={t}>{t}</Badge>
          ))}
        </div>
      )}

      {project.faq.length > 0 && (
        <Card className="mt-6">
          <h2 className="mb-2 font-medium">Frequently Asked Questions</h2>
          <div className="space-y-4">
            {project.faq.map((item, i) => (
              <div key={i}>
                <p className="text-sm font-medium">{item.question}</p>
                <p className="mt-1 text-sm text-muted">{item.answer}</p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
