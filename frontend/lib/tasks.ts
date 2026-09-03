import { apiFetch } from "@/lib/api-client";
import type {
  Task,
  TaskCreatePayload,
  TaskListFilters,
  TaskListResponse,
  TaskUpdatePayload,
} from "@/lib/types";

function buildQuery(filters: TaskListFilters, extra: Record<string, string | number> = {}): string {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  for (const s of filters.status ?? []) params.append("status", s);
  for (const p of filters.priority ?? []) params.append("priority", p);
  if (filters.include_subtasks) params.set("include_subtasks", "true");
  if (filters.sort) params.set("sort", filters.sort);
  if (filters.order) params.set("order", filters.order);
  for (const [k, v] of Object.entries(extra)) params.set(k, String(v));
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export async function listProjectTasks(
  projectId: string,
  filters: TaskListFilters = {},
  page = 1,
  pageSize = 100,
): Promise<TaskListResponse> {
  const query = buildQuery(filters, { page, page_size: pageSize });
  return apiFetch<TaskListResponse>(`projects/${projectId}/tasks${query}`);
}

export async function createTask(projectId: string, payload: TaskCreatePayload): Promise<Task> {
  return apiFetch<Task>(`projects/${projectId}/tasks`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateTask(taskId: string, payload: TaskUpdatePayload): Promise<Task> {
  return apiFetch<Task>(`tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteTask(taskId: string): Promise<void> {
  return apiFetch<void>(`tasks/${taskId}`, { method: "DELETE" });
}

export async function reorderTasks(
  projectId: string,
  status: string,
  taskIds: string[],
  parentId: string | null = null,
): Promise<TaskListResponse> {
  return apiFetch<TaskListResponse>(`projects/${projectId}/tasks/reorder`, {
    method: "POST",
    body: JSON.stringify({ status, parent_id: parentId, task_ids: taskIds }),
  });
}
