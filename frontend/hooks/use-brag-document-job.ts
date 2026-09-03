"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useJobPoll } from "@/hooks/use-job-poll";
import { cancelBragDocumentJob, getBragDocumentJob, listBragDocumentJobs } from "@/lib/brag-documents";

export function bragDocumentJobKey(jobId: string | null) {
  return ["brag-document-job", jobId] as const;
}

const BRAG_DOCUMENT_LIST_KEY = ["brag-document-jobs"] as const;

/** The saved-documents list shown on the Brag Documents page when no specific job is
 * open — a plain fetch, not a poll, since it's just a history view. React Query's default
 * refetch-on-mount picks up anything created since the list was last shown (e.g. after
 * "Start over" -> generate -> back to the list) without any manual invalidation. */
export function useBragDocumentJobs() {
  return useQuery({ queryKey: BRAG_DOCUMENT_LIST_KEY, queryFn: listBragDocumentJobs });
}

/** Polls GET /brag-document-jobs/{id} until it lands on succeeded/failed/cancelled. Thin
 * wrapper over the shared useJobPoll (same underlying primitive as use-extraction-job.ts
 * and use-breakdown.ts's useBreakdownJob). */
export function useBragDocumentJob(jobId: string | null) {
  return useJobPoll(bragDocumentJobKey(jobId), () => getBragDocumentJob(jobId as string), jobId !== null);
}

export function useCancelBragDocumentJob(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => cancelBragDocumentJob(jobId),
    onSuccess: (job) => queryClient.setQueryData(bragDocumentJobKey(jobId), job),
  });
}
