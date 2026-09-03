"use client";

import { useQuery } from "@tanstack/react-query";
import type { JobStatus } from "@/lib/types";

const TERMINAL_STATUSES: JobStatus[] = ["succeeded", "failed", "cancelled"];
const POLL_INTERVAL_MS = 1200;

/** Generic "poll until terminal" query, shared by both extraction jobs and AI
 * work-breakdown jobs — they're two different tables/endpoints on the backend but the
 * exact same 4-stage state machine and poll shape (see backend/DESIGN.md §6). `enabled`
 * is the caller's own gate (e.g. "only once an id exists"); this hook never guesses it
 * from the query key. */
export function useJobPoll<T extends { status: JobStatus }>(
  queryKey: readonly unknown[],
  fetchJob: () => Promise<T>,
  enabled: boolean,
) {
  return useQuery({
    queryKey,
    queryFn: fetchJob,
    enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && TERMINAL_STATUSES.includes(status) ? false : POLL_INTERVAL_MS;
    },
  });
}
