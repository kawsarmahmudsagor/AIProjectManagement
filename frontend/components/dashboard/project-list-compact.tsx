import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { formatProjectRange } from "@/lib/dates";
import type { ProjectSummary } from "@/lib/types";

const MAX_VISIBLE_ROWS = 12;

/** RSC. Each row is a single <Link> with NO nested interactive children (deliberately no
 * delete button here) — that sidesteps the interactive-inside-Link hazard entirely
 * rather than reproducing DeleteProjectButton's preventDefault/stopPropagation
 * workaround a second time. Deletion stays on the /projects cards and the detail page. */
export function ProjectListCompact({ projects, total }: { projects: ProjectSummary[]; total: number }) {
  const visible = projects.slice(0, MAX_VISIBLE_ROWS);

  return (
    <Card padding="none">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h3 className="font-semibold">Projects</h3>
        <span className="text-sm text-muted">
          {total} project{total === 1 ? "" : "s"}
        </span>
      </div>
      {visible.length === 0 ? (
        <p className="p-4 text-sm text-muted">
          No projects yet.{" "}
          <Link href="/projects/new" className="text-accent hover:underline">
            Add your first one
          </Link>
          .
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {visible.map((project) => (
            <li key={project.id}>
              <Link href={`/projects/${project.id}`} className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-surface-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{project.name}</p>
                  <p className="truncate text-xs text-muted">
                    {project.role} · {formatProjectRange(project)}
                  </p>
                </div>
                {project.technologies.length > 0 && (
                  <div className="hidden shrink-0 gap-1.5 @lg:flex">
                    {project.technologies.slice(0, 3).map((t) => (
                      <Badge key={t}>{t}</Badge>
                    ))}
                  </div>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
      {total > visible.length && (
        <div className="border-t border-border px-4 py-2.5 text-center">
          <Link href="/projects" className="text-sm text-accent hover:underline">
            View all {total} projects →
          </Link>
        </div>
      )}
    </Card>
  );
}
