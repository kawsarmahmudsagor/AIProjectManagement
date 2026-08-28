"use client";

import { useQuery } from "@tanstack/react-query";
import { getExtractionJob } from "@/lib/documents";
import type { JobStatus } from "@/lib/types";

const TERMINAL_STATUSES: JobStatus[] = ["succeeded", "failed", "cancelled"];
const POLL_INTERVAL_MS = 1200;

/** Polls GET /extraction-jobs/{id} until it lands on succeeded/failed. `jobId` is null
 * before an upload starts — the query stays disabled until then. */
export function useExtractionJob(jobId: string | null) {
  return useQuery({
    queryKey: ["extraction-job", jobId],
    queryFn: () => getExtractionJob(jobId as string),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && TERMINAL_STATUSES.includes(status) ? false : POLL_INTERVAL_MS;
    },
  });
}
