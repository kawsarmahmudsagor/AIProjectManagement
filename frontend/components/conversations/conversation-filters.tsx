"use client";

import { ArrowDownAZ, ArrowUpAZ, Star } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";

export function ConversationFilters() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const starredOnly = searchParams.get("starred") === "true";
  const sort = searchParams.get("sort") === "asc" ? "asc" : "desc";

  function setParam(key: string, value: string | null) {
    const params = new URLSearchParams(searchParams);
    if (value === null) params.delete(key);
    else params.set(key, value);
    router.replace(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={() => setParam("starred", starredOnly ? null : "true")}
        aria-pressed={starredOnly}
        className={cn(
          "flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm hover:bg-surface-2",
          starredOnly ? "bg-surface-2 text-foreground" : "text-muted",
        )}
      >
        <Star size={14} className={cn(starredOnly && "fill-current")} />
        Starred
      </button>
      <button
        type="button"
        onClick={() => setParam("sort", sort === "asc" ? null : "asc")}
        aria-label={sort === "asc" ? "Sorted oldest first" : "Sorted newest first"}
        title={sort === "asc" ? "Oldest first" : "Newest first"}
        className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm text-muted hover:bg-surface-2"
      >
        {sort === "asc" ? <ArrowUpAZ size={14} /> : <ArrowDownAZ size={14} />}
        {sort === "asc" ? "Oldest first" : "Newest first"}
      </button>
    </div>
  );
}
