import { Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/** Marks a row as AI-generated. Cross-feature (tasks today, breakdown review later, the
 * generated-thumbnail badge on project cards), so it lives in ui/ rather than a feature
 * folder. Pure rendering — provenance is a persisted server column (Task.source,
 * ProjectMedia.origin), not client state to keep in sync.
 *
 * `title` defaults to the original AI-work-breakdown copy so every existing call site
 * (none of which passed a title) keeps its exact current tooltip; a new call site (e.g.
 * a generated thumbnail) passes its own. */
export function AiOriginBadge({
  className,
  title = "Created by the AI work breakdown",
}: {
  className?: string;
  title?: string;
}) {
  return (
    <Badge title={title} variant="accent" className={cn("gap-1", className)}>
      <Sparkles size={11} />
      AI
    </Badge>
  );
}
