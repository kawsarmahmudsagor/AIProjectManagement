import type { TaskListFilters } from "@/lib/types";

// Detail is ["task", id] (singular) on purpose: invalidateQueries({queryKey:
// taskKeys.project(id)}) must hit every filter variant of that project's list under
// ["tasks", projectId, ...] and nothing else — a ["tasks", "detail", id] key would sit
// inside that same prefix-match namespace by mistake.
export const taskKeys = {
  project: (projectId: string) => ["tasks", projectId] as const,
  list: (projectId: string, filters: TaskListFilters = {}) =>
    ["tasks", projectId, filters] as const,
  detail: (taskId: string) => ["task", taskId] as const,
};
