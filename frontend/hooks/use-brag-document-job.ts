"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useJobPoll } from "@/hooks/use-job-poll";
import {
  cancelBragDocumentJob,
  deleteBragDocumentJob,
  getBragDocumentJob,
  listBragDocumentJobs,
  resetBragDocumentEdits,
  updateBragDocumentResult,
} from "@/lib/brag-documents";
import type { BragDocumentJobListResponse, BragDocumentResult } from "@/lib/types";

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

/** Autosaves a manual edit (text change and/or a removed bullet/group/impact area) —
 * always sends the whole edited document, since the stored edit itself is one JSON blob
 * with no per-item ids to diff against. Updates the job-detail cache directly from the
 * response so the editor's "is this saved" state (and the Reset-changes affordance)
 * stays in sync without a refetch. */
export function useUpdateBragDocumentResult(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (result: BragDocumentResult) => updateBragDocumentResult(jobId, result),
    onSuccess: (job) => queryClient.setQueryData(bragDocumentJobKey(jobId), job),
  });
}

/** Discards every saved edit, reverting to the original LLM draft. */
export function useResetBragDocumentEdits(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => resetBragDocumentEdits(jobId),
    onSuccess: (job) => queryClient.setQueryData(bragDocumentJobKey(jobId), job),
  });
}

/** Removes the job from the cached list immediately (rather than just invalidating and
 * waiting on a refetch) so the row disappears from the history the instant the delete
 * confirms, same as project/task deletes elsewhere in this app. */
export function useDeleteBragDocumentJob(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => deleteBragDocumentJob(jobId),
    onSuccess: () => {
      queryClient.setQueryData<BragDocumentJobListResponse>(BRAG_DOCUMENT_LIST_KEY, (current) =>
        current
          ? { ...current, items: current.items.filter((job) => job.id !== jobId), total: current.total - 1 }
          : current,
      );
      queryClient.removeQueries({ queryKey: bragDocumentJobKey(jobId) });
    },
  });
}
