"use client";

import { useJobPoll } from "@/hooks/use-job-poll";
import { getThumbnailJob } from "@/lib/project-media";

/** Polls GET /thumbnail-jobs/{id} until it lands on succeeded/failed/cancelled — the
 * same generic "poll until terminal" shape already shared by extraction jobs
 * (hooks/use-extraction-job.ts) and AI work-breakdown jobs (hooks/use-job-poll.ts's own
 * docstring), so a third job type needs zero new polling logic. */
export function useThumbnailJob(jobId: string | null) {
  return useJobPoll(["thumbnail-job", jobId], () => getThumbnailJob(jobId as string), jobId !== null);
}
