"use client";

import { ChevronDown, ChevronRight, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { AiOriginBadge } from "@/components/ui/ai-origin-badge";
import { Select } from "@/components/ui/select";
import { PRIORITY_LABELS, PRIORITY_ORDER } from "@/components/tasks/task-constants";
import { ESTIMATE_SIZE_LABELS, minutesToHoursLabel } from "@/components/breakdown/breakdown-constants";
import type { RowDraft } from "@/components/breakdown/breakdown-reducer";
import { cn } from "@/lib/utils";

export function BreakdownRow({
  row,
  depth,
  onToggle,
  onToggleExpanded,
  onEdit,
  onReject,
}: {
  row: RowDraft;
  depth: number;
  onToggle: () => void;
  onToggleExpanded: () => void;
  onEdit: (patch: Partial<Pick<RowDraft, "title" | "description" | "priority" | "estimate_minutes">>) => void;
  onReject: () => void;
}) {
  const [draftHours, setDraftHours] = useState(() => minutesToHoursLabel(row.estimate_minutes));

  const readOnly = Boolean(row.createdTaskId) || row.rejected;
  const checked = Boolean(row.createdTaskId) || row.decision === "included";

  return (
    <li
      className={cn(
        "border-b border-border last:border-b-0",
        row.rejected && "opacity-40",
        row.createdTaskId && "bg-success/5",
      )}
      style={{ paddingLeft: depth * 24 }}
    >
      <div className="flex items-center gap-2 px-3 py-2.5">
        <button
          type="button"
          onClick={onToggleExpanded}
          aria-label={row.expanded ? "Collapse" : "Expand"}
          className="shrink-0 text-muted hover:text-foreground"
        >
          {row.expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>

        <input
          type="checkbox"
          checked={checked}
          disabled={readOnly}
          onChange={onToggle}
          aria-label={`Include "${row.title}"`}
          className="size-4 shrink-0 rounded border-border accent-accent"
        />

        <button
          type="button"
          onClick={onToggleExpanded}
          className={cn("flex-1 truncate text-left text-sm", row.rejected && "line-through")}
        >
          {row.title}
        </button>

        {row.grounded ? (
          <span className="shrink-0 text-xs text-muted" title="Directly stated in your document">
            Grounded
          </span>
        ) : (
          <span
            className="flex shrink-0 items-center gap-1 text-xs text-muted"
            title="Not directly stated — a reasonable suggestion"
          >
            <Sparkles size={11} /> Suggested
          </span>
        )}

        {row.createdTaskId ? (
          <AiOriginBadge />
        ) : (
          <>
            <Select
              value={row.priority}
              disabled={readOnly}
              onChange={(e) => onEdit({ priority: e.target.value as RowDraft["priority"] })}
              aria-label="Priority"
              className="min-w-[6rem] shrink-0"
            >
              {PRIORITY_ORDER.map((p) => (
                <option key={p} value={p}>
                  {PRIORITY_LABELS[p]}
                </option>
              ))}
            </Select>
            {!row.rejected && (
              <button
                type="button"
                onClick={onReject}
                aria-label={`Reject "${row.title}"`}
                className="shrink-0 text-muted hover:text-danger"
              >
                <X size={14} />
              </button>
            )}
          </>
        )}
      </div>

      {row.expanded && (
        <div className="space-y-3 border-t border-border bg-surface-2/30 px-3 py-3" style={{ marginLeft: 22 }}>
          {row.createdTaskId ? (
            <p className="text-xs text-muted">Added to your task list — no longer editable here.</p>
          ) : (
            <>
              <textarea
                value={row.description}
                disabled={readOnly}
                onChange={(e) => onEdit({ description: e.target.value })}
                rows={2}
                placeholder="Description…"
                className="w-full rounded-lg border border-border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50"
              />
              <div className="flex items-center gap-3">
                {row.estimate_size && (
                  <span className="text-xs text-muted" title="The AI's rough size estimate">
                    Size: {ESTIMATE_SIZE_LABELS[row.estimate_size]}
                  </span>
                )}
                <label className="flex items-center gap-1.5 text-xs text-muted">
                  Hours:
                  <input
                    type="text"
                    inputMode="decimal"
                    disabled={readOnly}
                    value={draftHours}
                    onChange={(e) => setDraftHours(e.target.value)}
                    onBlur={() => {
                      const hours = Number.parseFloat(draftHours.replace(/[^0-9.]/g, ""));
                      const minutes = Number.isFinite(hours) && hours > 0 ? Math.round(hours * 60) : null;
                      onEdit({ estimate_minutes: minutes });
                      setDraftHours(minutesToHoursLabel(minutes));
                    }}
                    className="w-16 rounded-lg border border-border bg-background px-2 py-1 text-sm"
                  />
                </label>
              </div>
              {row.grounded && row.source_quote && (
                <details className="text-xs text-muted">
                  <summary className="cursor-pointer select-none">Why?</summary>
                  <blockquote className="mt-1 border-l-2 border-border pl-2 italic">
                    &ldquo;{row.source_quote}&rdquo;
                  </blockquote>
                </details>
              )}
            </>
          )}
        </div>
      )}
    </li>
  );
}
