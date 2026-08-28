"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, FolderKanban } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { apiFetch } from "@/lib/api-client";
import type { ProjectListResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

export const PROJECTS_NAV_QUERY_KEY = ["projects", "nav"] as const;

export function ProjectsNavSection({ collapsed = false }: { collapsed?: boolean }) {
  const pathname = usePathname();
  const [expanded, setExpanded] = useState(false);
  const isActive = pathname.startsWith("/projects");

  const { data, isLoading, isError } = useQuery({
    queryKey: PROJECTS_NAV_QUERY_KEY,
    queryFn: () => apiFetch<ProjectListResponse>("projects?page=1&page_size=100"),
    enabled: expanded && !collapsed,
  });

  if (collapsed) {
    return (
      <Link
        href="/projects"
        title="Projects"
        className={cn(
          "flex items-center justify-center rounded-lg px-2 py-2 text-sm text-muted hover:bg-surface-2 hover:text-foreground",
          isActive && "bg-surface-2 text-foreground",
        )}
      >
        <FolderKanban size={16} />
      </Link>
    );
  }

  return (
    <div>
      <div
        className={cn(
          "flex items-center rounded-lg text-sm text-muted hover:bg-surface-2 hover:text-foreground",
          isActive && "bg-surface-2 text-foreground",
        )}
      >
        <Link href="/projects" className="flex flex-1 items-center gap-2 px-3 py-2">
          <FolderKanban size={16} />
          Projects
        </Link>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-label={expanded ? "Collapse projects list" : "Expand projects list"}
          aria-expanded={expanded}
          className="px-2 py-2 text-muted hover:text-foreground"
        >
          <ChevronDown size={14} className={cn("transition-transform", !expanded && "-rotate-90")} />
        </button>
      </div>

      {expanded && (
        <div className="ml-6 mt-1 space-y-0.5 border-l border-border pl-3">
          {isLoading && <p className="px-2 py-1 text-xs text-muted">Loading…</p>}
          {isError && <p className="px-2 py-1 text-xs text-danger">Couldn&apos;t load projects</p>}
          {data?.items.length === 0 && <p className="px-2 py-1 text-xs text-muted">No projects yet</p>}
          {data?.items.map((project) => {
            const href = `/projects/${project.id}`;
            return (
              <Link
                key={project.id}
                href={href}
                title={project.name}
                className={cn(
                  "block truncate rounded-md px-2 py-1 text-xs text-muted hover:bg-surface-2 hover:text-foreground",
                  pathname === href && "bg-surface-2 text-foreground",
                )}
              >
                {project.name}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
