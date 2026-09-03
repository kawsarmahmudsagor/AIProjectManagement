"use client";

import { useJobPoll } from "@/hooks/use-job-poll";
import { getExtractionJob } from "@/lib/documents";

/** Polls GET /extraction-jobs/{id} until it lands on succeeded/failed/cancelled. `jobId`
 * is null before an upload starts — the query stays disabled until then. Thin wrapper
 * over the generic useJobPoll (shared with AI work-breakdown jobs) so this call site and
 * its external behavior are unchanged. */
export function useExtractionJob(jobId: string | null) {
  return useJobPoll(["extraction-job", jobId], () => getExtractionJob(jobId as string), jobId !== null);
}
