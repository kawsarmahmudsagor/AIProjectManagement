import Link from "next/link";
import { Card } from "@/components/ui/card";
import type { ProjectSummary } from "@/lib/types";

function formatRange(p: ProjectSummary) {
  const fmt = (d: string) => new Date(d).toLocaleDateString("en-US", { month: "short", year: "numeric" });
  return `${fmt(p.start_date)} – ${p.is_current ? "Present" : p.end_date ? fmt(p.end_date) : ""}`;
}

export function ProjectCard({ project }: { project: ProjectSummary }) {
  return (
    <Link href={`/projects/${project.id}`}>
      <Card className="h-full transition-colors hover:border-accent/60">
        <h3 className="font-semibold">{project.name}</h3>
        <p className="text-sm text-muted">{project.role}</p>
        <p className="mt-1 text-xs text-muted">{formatRange(project)}</p>
        {project.short_summary_text && (
          <p className="mt-3 line-clamp-3 text-sm text-foreground/90">{project.short_summary_text}</p>
        )}
      </Card>
    </Link>
  );
}
