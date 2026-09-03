"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useJobPoll } from "@/hooks/use-job-poll";
import { useToast } from "@/components/ui/toaster";
import { taskKeys } from "@/lib/task-keys";
import {
  acceptBreakdownItems,
  cancelBreakdownJob,
  createBreakdown,
  dismissBreakdownRefs,
  getBreakdownJob,
} from "@/lib/breakdown";
import type { BreakdownAcceptItem, BreakdownCreatePayload } from "@/lib/types";

export function breakdownJobKey(jobId: string | null) {
  return ["breakdown-job", jobId] as const;
}

export function useBreakdownJob(jobId: string | null) {
  return useJobPoll(breakdownJobKey(jobId), () => getBreakdownJob(jobId as string), jobId !== null);
}

export function useCreateBreakdown(projectId: string) {
  const { toast } = useToast();
  return useMutation({
    mutationFn: (payload: BreakdownCreatePayload) => createBreakdown(projectId, payload),
    onError: () => toast({ variant: "error", message: "Couldn't start the breakdown. Try again." }),
  });
}

export function useCancelBreakdownJob(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => cancelBreakdownJob(jobId),
    onSuccess: (job) => queryClient.setQueryData(breakdownJobKey(jobId), job),
  });
}

/** Never optimistic and never hand-inserted into the task list cache — accepted tasks
 * come back without the position the server actually assigned them, and a partial
 * accept can fail per-item, so an invalidate-and-refetch is the only version of this
 * that stays correct (backend/DESIGN.md §8). The job itself is also invalidated: its
 * `accepted` map is what the review UI uses to mark rows "Added" across a refresh or a
 * second partial pass. */
export function useAcceptBreakdownItems(projectId: string, jobId: string) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation({
    mutationFn: (items: BreakdownAcceptItem[]) => acceptBreakdownItems(jobId, items),
    onSuccess: (res) => {
      if (res.created.length > 0) {
        queryClient.invalidateQueries({ queryKey: taskKeys.project(projectId) });
      }
      queryClient.invalidateQueries({ queryKey: breakdownJobKey(jobId) });
    },
    onError: () => toast({ variant: "error", message: "Couldn't add those tasks. Try again." }),
  });
}

export function useDismissBreakdownRefs(jobId: string) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation({
    mutationFn: (refs: string[]) => dismissBreakdownRefs(jobId, refs),
    onSuccess: (job) => queryClient.setQueryData(breakdownJobKey(jobId), job),
    onError: () => toast({ variant: "error", message: "Couldn't save that. Try again." }),
  });
}
