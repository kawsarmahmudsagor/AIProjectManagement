import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { DashboardTechnology } from "@/lib/types";

/** RSC — a clickable chip cloud needs no client interactivity (Link + a plain <span>
 * Badge both work server-rendered). Clicking a chip filters /projects by that
 * technology (backend/app/routers/projects.py's `technology=` query param). */
export function SkillsSummaryCard({ technologies }: { technologies: DashboardTechnology[] }) {
  return (
    <Card>
      <h3 className="font-semibold">Skills across your projects</h3>
      {technologies.length === 0 ? (
        <p className="mt-3 text-sm text-muted">
          No technologies yet — add some to your projects and they&apos;ll show up here.
        </p>
      ) : (
        <div className="mt-3 flex max-h-[168px] flex-wrap gap-2 overflow-y-auto pr-1">
          {technologies.map((tech) => (
            <Link key={tech.name} href={`/projects?technology=${encodeURIComponent(tech.name)}`}>
              <Badge className="gap-1.5 border border-transparent transition-colors hover:border-accent/60">
                <span className="text-foreground">{tech.name}</span>
                <span className="tabular-nums text-muted">{tech.project_count}</span>
              </Badge>
            </Link>
          ))}
        </div>
      )}
    </Card>
  );
}
