import { Download, FileText, Pencil } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, Badge } from "@/components/ui/card";
import { DeleteProjectButton } from "@/components/projects/delete-project-button";
import { serverApiFetch } from "@/lib/server-api";
import type { Project } from "@/lib/types";

function formatDate(d: string) {
  return new Date(d).toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

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
    </div>
  );
}
