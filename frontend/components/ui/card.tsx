import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

// Re-exported so existing `import { Card, Badge } from "@/components/ui/card"` call
// sites keep working after Badge moved to its own file (components/ui/badge.tsx) with
// its own variant system.
export { Badge } from "@/components/ui/badge";

type Elevation = 0 | 1 | 2;
type Padding = "none" | "sm" | "md";

const ELEVATIONS: Record<Elevation, string> = {
  0: "",
  1: "shadow-elevation-1",
  2: "shadow-elevation-2",
};

const PADDINGS: Record<Padding, string> = {
  none: "p-0",
  sm: "p-4",
  md: "p-6",
};

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Shadow depth on top of the base border — 0 (default, flat/bordered, matches every
   * existing Card in the app) through 2 (a raised panel like a dropdown or dialog body). */
  elevation?: Elevation;
  /** Adds the hover/focus treatment used by clickable cards (ProjectCard, the dashboard's
   * RecentConversationsCard) without repeating `transition-colors hover:border-accent/60`
   * at every call site. */
  interactive?: boolean;
  /** `md` (24px, the original hardcoded p-6) is the default so nothing already using
   * Card needs to change; `sm`/`none` are for denser surfaces (list rows, the project
   * card's media-topped layout) that used to fight the hardcoded padding with `p-0`. */
  padding?: Padding;
}

export function Card({ className, elevation = 0, interactive = false, padding = "md", ...props }: CardProps) {
  return (
    <div
      className={cn(
        // Translucent + blurred rather than a flat bg-surface — lets the page
        // background's accent glow (globals.css body rule) show through softly, the
        // "frosted glass" look. backdrop-blur needs its own stacking context to look
        // right over content that scrolls behind it, hence isolate.
        "isolate rounded-xl border border-border bg-surface/60 backdrop-blur-md",
        PADDINGS[padding],
        ELEVATIONS[elevation],
        interactive && "transition-colors hover:border-accent/60",
        className,
      )}
      {...props}
    />
  );
}
