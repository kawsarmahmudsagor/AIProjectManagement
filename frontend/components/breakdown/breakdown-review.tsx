"use client";

import { useEffect, useMemo, useReducer } from "react";
import { Button } from "@/components/ui/button";
import { useAcceptBreakdownItems, useDismissBreakdownRefs } from "@/hooks/use-breakdown";
import {
  breakdownReducer,
  buildAcceptItems,
  childRefs,
  includedRefs,
  initBreakdownState,
  promotionCandidates,
  selectableRefs,
  subtreeRefs,
} from "@/components/breakdown/breakdown-reducer";
import { BreakdownRow } from "@/components/breakdown/breakdown-row";
import type { BreakdownJob } from "@/lib/types";

export function BreakdownReview({ projectId, job }: { projectId: string; job: BreakdownJob }) {
  const result = job.result;
  const [state, dispatch] = useReducer(
    breakdownReducer,
    undefined,
    () => initBreakdownState(result ?? { tasks: [], confidence_notes: [] }, job),
  );

  // Re-sync createdTaskId/rejected whenever a fresh job comes in (after accept/dismiss or
  // the next poll tick), without resetting in-flight edits — see the reducer's
  // syncFromJob for what's preserved. The reducer itself no-ops (returns the same state
  // reference) when nothing actually changed, so this doesn't cause an extra render on
  // every poll tick.
  useEffect(() => {
    dispatch({ type: "sync_job", job });
  }, [job]);

  const accept = useAcceptBreakdownItems(projectId, job.id);
  const dismiss = useDismissBreakdownRefs(job.id);

  const included = useMemo(() => includedRefs(state), [state]);
  const selectable = useMemo(() => selectableRefs(state), [state]);
  const promoted = useMemo(() => promotionCandidates(state), [state]);

  const topLevelRefs = state.order.filter((ref) => !state.rows[ref]?.parent_ref);
  const groundedTop = topLevelRefs.filter((ref) => state.rows[ref]?.grounded);
  const ungroundedTop = topLevelRefs.filter((ref) => !state.rows[ref]?.grounded);

  const allDone = state.order.length > 0 && state.order.every((ref) => {
    const row = state.rows[ref];
    return row?.createdTaskId || row?.rejected;
  });

  function renderGroup(refs: string[]) {
    return refs.flatMap((ref) => {
      const row = state.rows[ref];
      if (!row) return [];
      const kids = childRefs(state, ref);
      return [
        <BreakdownRow
          key={ref}
          row={row}
          depth={0}
          onToggle={() => dispatch({ type: "toggle", ref })}
          onToggleExpanded={() => dispatch({ type: "toggle_expanded", ref })}
          onEdit={(patch) => dispatch({ type: "edit", ref, patch })}
          onReject={() => {
            const refs = subtreeRefs(state, ref);
            dispatch({ type: "reject_subtree", refs });
            void dismiss.mutate(refs);
          }}
        />,
        ...kids.map((childRef) => {
          const childRow = state.rows[childRef];
          if (!childRow) return null;
          return (
            <BreakdownRow
              key={childRef}
              row={childRow}
              depth={1}
              onToggle={() => dispatch({ type: "toggle", ref: childRef })}
              onToggleExpanded={() => dispatch({ type: "toggle_expanded", ref: childRef })}
              onEdit={(patch) => dispatch({ type: "edit", ref: childRef, patch })}
              onReject={() => {
                const refs = subtreeRefs(state, childRef);
                dispatch({ type: "reject_subtree", refs });
                void dismiss.mutate(refs);
              }}
            />
          );
        }),
      ];
    });
  }

  if (!result || state.order.length === 0) {
    return <p className="text-sm text-muted">The AI didn&apos;t propose any tasks from this input.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="sticky top-0 z-10 space-y-2 border-b border-border bg-background pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-medium">
            {included.length} of {selectable.length} selected
          </p>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => dispatch({ type: "set_many", refs: selectable, decision: "pending" })}
              disabled={included.length === 0}
            >
              None
            </Button>
            <Button
              type="button"
              onClick={() => {
                const items = buildAcceptItems(state, included);
                accept.mutate(items);
              }}
              disabled={included.length === 0 || accept.isPending}
            >
              {accept.isPending ? "Adding…" : `Accept ${included.length}`}
            </Button>
          </div>
        </div>
        <p className="text-xs text-muted">
          Capped at {job.max_tasks} tasks. Nothing has been created yet until you accept.
        </p>
      </div>

      {promoted.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-warning/40 bg-warning/5 px-3 py-2 text-sm">
          <span>
            {promoted.length} selected subtask{promoted.length > 1 ? "s" : ""} will be added as top-level tasks
            because {promoted.length > 1 ? "their parents aren't" : "its parent isn't"} selected.
          </span>
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              const parentRefs = promoted
                .map((ref) => state.rows[ref]?.parent_ref)
                .filter((r): r is string => Boolean(r));
              dispatch({ type: "set_many", refs: parentRefs, decision: "included" });
            }}
          >
            Include their parent{promoted.length > 1 ? "s" : ""} instead
          </Button>
        </div>
      )}

      {job.result?.confidence_notes && job.result.confidence_notes.length > 0 && (
        <ul className="space-y-1 rounded-lg border border-border bg-surface-2/30 px-3 py-2 text-xs text-muted">
          {job.result.confidence_notes.map((note, i) => (
            <li key={i}>{note}</li>
          ))}
        </ul>
      )}

      {job.is_scanned && (
        <p className="text-xs text-muted">
          This looked like a scanned document — quoted source text may be approximate.
        </p>
      )}

      <ul className="overflow-hidden rounded-xl border border-border">{renderGroup(groundedTop)}</ul>

      {ungroundedTop.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-muted">Suggested additions — not in your document</h3>
          <ul className="overflow-hidden rounded-xl border border-border">{renderGroup(ungroundedTop)}</ul>
        </div>
      )}

      {allDone && <p className="text-sm text-muted">Every proposed task has been added or rejected.</p>}
    </div>
  );
}
