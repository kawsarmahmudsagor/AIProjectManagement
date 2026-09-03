import { cn } from "@/lib/utils";

/** A row of thin progress segments, one per stage, lit up through `currentIndex` while
 * `active`. Extracted from document-upload.tsx so the AI work-breakdown flow (which
 * polls a different job table but the same 4-stage queued/parsing/extracting/structuring
 * shape) can reuse it instead of re-implementing the same markup with different labels. */
export function JobStageStepper({
  stages,
  currentIndex,
  active,
}: {
  stages: readonly string[];
  currentIndex: number;
  active: boolean;
}) {
  return (
    <div className="flex gap-1.5">
      {stages.map((stage, i) => (
        <div
          key={stage}
          className={cn("h-1 flex-1 rounded-full bg-surface-2", i <= currentIndex && active && "bg-accent")}
        />
      ))}
    </div>
  );
}
