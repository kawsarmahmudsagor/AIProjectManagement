import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { DeleteProjectButton } from "@/components/projects/delete-project-button";
import { ProjectCardMedia } from "@/components/projects/project-card-media";
import { formatProjectRange } from "@/lib/dates";
import type { ProjectSummary } from "@/lib/types";

const MAX_VISIBLE_TECHNOLOGIES = 4;

/** RSC — only the media area (hover-to-play video) needs client interactivity, isolated
 * in ProjectCardMedia so this component's own payload stays server-rendered. The
 * DeleteProjectButton keeps working nested inside the wrapping <Link> the same way it
 * always has (its own preventDefault/stopPropagation wrapper) — the media area adds NO
 * interactive descendants of its own (the video is pointer-events-none, the video badge
 * is aria-hidden), so this doesn't add a second nested-interactive-in-Link hazard. */
export function ProjectCard({ project }: { project: ProjectSummary }) {
  const technologies = project.technologies ?? [];
  const visibleTech = technologies.slice(0, MAX_VISIBLE_TECHNOLOGIES);
  const hiddenTechCount = technologies.length - visibleTech.length;

  return (
    <Link href={`/projects/${project.id}`} className="group block h-full">
      <Card padding="none" elevation={0} interactive className="relative flex h-full flex-col overflow-hidden">
        <div className="absolute right-3 top-3 z-10">
          <DeleteProjectButton projectId={project.id} projectName={project.name} iconOnly />
        </div>
        <ProjectCardMedia
          thumbnailUrl={project.thumbnail_url ?? null}
          videoUrl={project.video_url ?? null}
          alt={project.name}
        />
        <div className="flex flex-1 flex-col gap-1 p-4">
          <h3 className="pr-8 text-lg font-semibold leading-tight">{project.name}</h3>
          <p className="text-sm text-muted">{project.role}</p>
          <p className="text-xs text-muted">{formatProjectRange(project)}</p>
          {project.short_summary_text && (
            <p className="mt-2 line-clamp-2 text-sm text-foreground/90">{project.short_summary_text}</p>
          )}
          {visibleTech.length > 0 && (
            <div className="mt-auto flex flex-wrap gap-1.5 pt-3">
              {visibleTech.map((t) => (
                <Badge key={t}>{t}</Badge>
              ))}
              {hiddenTechCount > 0 && <Badge>+{hiddenTechCount}</Badge>}
            </div>
          )}
        </div>
      </Card>
    </Link>
  );
}
