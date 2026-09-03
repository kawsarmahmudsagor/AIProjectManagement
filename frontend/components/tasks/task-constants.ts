import type { TaskPriority, TaskStatus } from "@/lib/types";

export const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  blocked: "Blocked",
  done: "Done",
};

export const STATUS_ORDER: TaskStatus[] = ["todo", "in_progress", "blocked", "done"];

export const STATUS_DOT: Record<TaskStatus, string> = {
  todo: "bg-muted",
  in_progress: "bg-accent",
  blocked: "bg-warning",
  done: "bg-success",
};

export const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  urgent: "Urgent",
};

export const PRIORITY_ORDER: TaskPriority[] = ["low", "medium", "high", "urgent"];
