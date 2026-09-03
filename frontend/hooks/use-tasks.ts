"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/components/ui/toaster";
import { taskKeys } from "@/lib/task-keys";
import { createTask, deleteTask, listProjectTasks, reorderTasks, updateTask } from "@/lib/tasks";
import type {
  TaskCreatePayload,
  TaskListFilters,
  TaskListResponse,
  TaskSummary,
  TaskUpdatePayload,
} from "@/lib/types";

export function useProjectTasks(
  projectId: string,
  filters: TaskListFilters = {},
  initialData?: TaskListResponse,
) {
  return useQuery({
    queryKey: taskKeys.list(projectId, filters),
    queryFn: () => listProjectTasks(projectId, filters),
    initialData,
  });
}

export function useCreateTask(projectId: string) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation({
    mutationFn: (payload: TaskCreatePayload) => createTask(projectId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: taskKeys.project(projectId) });
    },
    onError: () => {
      toast({ variant: "error", message: "Couldn't create the task. Try again." });
    },
  });
}

export function useUpdateTask(projectId: string) {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: ({ taskId, payload }: { taskId: string; payload: TaskUpdatePayload }) =>
      updateTask(taskId, payload),
    onMutate: async ({ taskId, payload }) => {
      await queryClient.cancelQueries({ queryKey: taskKeys.project(projectId) });
      const previous = queryClient.getQueriesData<TaskListResponse>({
        queryKey: taskKeys.project(projectId),
      });
      queryClient.setQueriesData<TaskListResponse>(
        { queryKey: taskKeys.project(projectId) },
        (old) => {
          if (!old) return old;
          return {
            ...old,
            items: old.items.map((t) =>
              t.id === taskId ? ({ ...t, ...payload } as TaskSummary) : t,
            ),
          };
        },
      );
      return { previous };
    },
    onError: (_err, _vars, context) => {
      context?.previous.forEach(([key, data]) => queryClient.setQueryData(key, data));
      toast({ variant: "error", message: "Couldn't save that change — restored the previous value." });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: taskKeys.project(projectId) });
    },
  });
}

export function useDeleteTask(projectId: string) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation({
    mutationFn: (taskId: string) => deleteTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: taskKeys.project(projectId) });
    },
    onError: () => {
      toast({ variant: "error", message: "Couldn't delete the task. Try again." });
    },
  });
}

export function useReorderTasks(projectId: string) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation({
    mutationFn: ({ status, taskIds }: { status: string; taskIds: string[] }) =>
      reorderTasks(projectId, status, taskIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: taskKeys.project(projectId) });
    },
    onError: () => {
      toast({ variant: "error", message: "Couldn't reorder tasks. Try again." });
    },
  });
}
