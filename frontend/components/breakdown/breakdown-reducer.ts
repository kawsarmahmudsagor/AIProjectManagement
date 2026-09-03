import { ESTIMATE_SIZE_MINUTES } from "@/components/breakdown/breakdown-constants";
import type { BreakdownJob, BreakdownResult, EstimateSize, TaskPriority } from "@/lib/types";

export type RowDecision = "pending" | "included";

export type RowDraft = {
  ref: string;
  title: string;
  description: string;
  priority: TaskPriority;
  estimate_size: EstimateSize | null;
  estimate_minutes: number | null;
  phase: string | null;
  parent_ref: string | null;
  grounded: boolean;
  source_quote: string | null;
  decision: RowDecision;
  // Explicit reject (not just "left unchecked") — persisted via dismissBreakdownRefs so
  // it survives a refresh instead of resetting to pending.
  rejected: boolean;
  // Set once job.accepted has this ref — read-only from that point on.
  createdTaskId: string | null;
  expanded: boolean;
};

export type BreakdownState = {
  order: string[]; // refs, original model order
  rows: Record<string, RowDraft>;
};

export function initBreakdownState(result: BreakdownResult, job: BreakdownJob): BreakdownState {
  const rows: Record<string, RowDraft> = {};
  const order: string[] = [];
  for (const t of result.tasks) {
    order.push(t.ref);
    rows[t.ref] = {
      ref: t.ref,
      title: t.title,
      description: t.description,
      priority: t.priority,
      estimate_size: t.estimate_size,
      estimate_minutes: t.estimate_size ? ESTIMATE_SIZE_MINUTES[t.estimate_size] : null,
      phase: t.phase,
      parent_ref: t.parent_ref,
      grounded: t.grounded,
      source_quote: t.source_quote,
      decision: "pending",
      rejected: job.dismissed_refs.includes(t.ref),
      createdTaskId: job.accepted[t.ref] ?? null,
      expanded: false,
    };
  }
  return { order, rows };
}

/** Re-syncs createdTaskId/rejected from a freshly-polled job (after accept/dismiss)
 * without clobbering in-flight local edits — title/description/priority/decision/expanded
 * all stay whatever the user currently has. Only ever called through the "sync_job"
 * reducer action below, never applied to state directly from a component. */
function syncFromJob(state: BreakdownState, job: BreakdownJob): BreakdownState {
  let changed = false;
  const rows = { ...state.rows };
  for (const ref of state.order) {
    const row = rows[ref];
    if (!row) continue;
    const createdTaskId = job.accepted[ref] ?? null;
    const rejected = row.rejected || job.dismissed_refs.includes(ref);
    if (row.createdTaskId !== createdTaskId || row.rejected !== rejected) {
      rows[ref] = { ...row, createdTaskId, rejected };
      changed = true;
    }
  }
  return changed ? { ...state, rows } : state;
}

type EditPatch = Partial<Pick<RowDraft, "title" | "description" | "priority" | "estimate_minutes">>;

type Action =
  | { type: "toggle"; ref: string }
  | { type: "set_many"; refs: string[]; decision: RowDecision }
  | { type: "edit"; ref: string; patch: EditPatch }
  | { type: "toggle_expanded"; ref: string }
  | { type: "reject_subtree"; refs: string[] }
  | { type: "sync_job"; job: BreakdownJob };

export function childRefs(state: BreakdownState, ref: string): string[] {
  return state.order.filter((r) => state.rows[r]?.parent_ref === ref);
}

export function subtreeRefs(state: BreakdownState, ref: string): string[] {
  const kids = childRefs(state, ref);
  return [ref, ...kids.flatMap((k) => subtreeRefs(state, k))];
}

export function breakdownReducer(state: BreakdownState, action: Action): BreakdownState {
  switch (action.type) {
    case "toggle": {
      const row = state.rows[action.ref];
      if (!row || row.createdTaskId || row.rejected) return state;
      return {
        ...state,
        rows: {
          ...state.rows,
          [action.ref]: { ...row, decision: row.decision === "included" ? "pending" : "included" },
        },
      };
    }
    case "set_many": {
      const rows = { ...state.rows };
      for (const ref of action.refs) {
        const row = rows[ref];
        if (!row || row.createdTaskId || row.rejected) continue;
        rows[ref] = { ...row, decision: action.decision };
      }
      return { ...state, rows };
    }
    case "edit": {
      const row = state.rows[action.ref];
      if (!row) return state;
      return { ...state, rows: { ...state.rows, [action.ref]: { ...row, ...action.patch } } };
    }
    case "toggle_expanded": {
      const row = state.rows[action.ref];
      if (!row) return state;
      return { ...state, rows: { ...state.rows, [action.ref]: { ...row, expanded: !row.expanded } } };
    }
    case "reject_subtree": {
      const rows = { ...state.rows };
      for (const ref of action.refs) {
        const row = rows[ref];
        if (!row || row.createdTaskId) continue;
        rows[ref] = { ...row, rejected: true, decision: "pending" };
      }
      return { ...state, rows };
    }
    case "sync_job":
      return syncFromJob(state, action.job);
    default:
      return state;
  }
}

// --- Selectors -----------------------------------------------------------------

export function includedRefs(state: BreakdownState): string[] {
  return state.order.filter((ref) => {
    const row = state.rows[ref];
    return row && row.decision === "included" && !row.rejected && !row.createdTaskId;
  });
}

export function selectableRefs(state: BreakdownState): string[] {
  return state.order.filter((ref) => {
    const row = state.rows[ref];
    return row && !row.createdTaskId && !row.rejected;
  });
}

/** Included rows whose parent isn't itself included and isn't already an accepted task —
 * these will be created as top-level tasks. Surfaced as a warning strip with a one-click
 * "include their parents too" fix, rather than either silently promoting or blocking the
 * whole accept (backend/DESIGN.md §8). */
export function promotionCandidates(state: BreakdownState): string[] {
  return includedRefs(state).filter((ref) => {
    const row = state.rows[ref];
    if (!row.parent_ref) return false;
    const parent = state.rows[row.parent_ref];
    if (!parent) return true;
    return parent.createdTaskId === null && parent.decision !== "included";
  });
}

export function buildAcceptItems(
  state: BreakdownState,
  refs: string[],
): {
  ref: string;
  parent_ref: string | null;
  title: string;
  description: string;
  priority: TaskPriority;
  estimate_minutes: number | null;
  estimate_size: EstimateSize | null;
}[] {
  const refSet = new Set(refs);
  return refs.map((ref) => {
    const row = state.rows[ref];
    const parentInBatch = row.parent_ref ? refSet.has(row.parent_ref) : false;
    const parentAlreadyCreated = row.parent_ref ? Boolean(state.rows[row.parent_ref]?.createdTaskId) : false;
    return {
      ref: row.ref,
      parent_ref: parentInBatch || parentAlreadyCreated ? row.parent_ref : null,
      title: row.title,
      description: row.description,
      priority: row.priority,
      estimate_minutes: row.estimate_minutes,
      estimate_size: row.estimate_size,
    };
  });
}
