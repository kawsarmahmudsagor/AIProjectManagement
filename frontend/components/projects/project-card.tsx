import Link from "next/link";
import { Card } from "@/components/ui/card";
import { DeleteProjectButton } from "@/components/projects/delete-project-button";
import { formatMonthYear } from "@/lib/dates";
import type { ProjectSummary } from "@/lib/types";

function formatRange(p: ProjectSummary) {
  return `${formatMonthYear(p.start_date)} – ${p.is_current ? "Present" : p.end_date ? formatMonthYear(p.end_date) : ""}`;
}

export function ProjectCard({ project }: { project: ProjectSummary }) {
  return (
    <Link href={`/projects/${project.id}`}>
      <Card className="relative h-full transition-colors hover:border-accent/60">
        <div className="absolute right-3 top-3">
          <DeleteProjectButton projectId={project.id} projectName={project.name} iconOnly />
        </div>
        <h3 className="pr-8 font-semibold">{project.name}</h3>
        <p className="text-sm text-muted">{project.role}</p>
        <p className="mt-1 text-xs text-muted">{formatRange(project)}</p>
        {project.short_summary_text && (
          <p className="mt-3 line-clamp-3 text-sm text-foreground/90">{project.short_summary_text}</p>
        )}
      </Card>
    </Link>
  );
}
