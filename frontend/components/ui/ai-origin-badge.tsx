import { Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/** Marks a row as AI-generated. Cross-feature (tasks today, breakdown review later), so
 * it lives in ui/ rather than a feature folder. Pure rendering — provenance is a
 * persisted server column (Task.source), not client state to keep in sync. */
export function AiOriginBadge({ className }: { className?: string }) {
  return (
    <Badge
      title="Created by the AI work breakdown"
      className={cn("gap-1 border border-accent/30 bg-accent/10 text-accent", className)}
    >
      <Sparkles size={11} />
      AI
    </Badge>
  );
}
