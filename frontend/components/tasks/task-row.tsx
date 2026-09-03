"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";
import { AiOriginBadge } from "@/components/ui/ai-origin-badge";
import { Badge } from "@/components/ui/card";
import { TaskPrioritySelect } from "@/components/tasks/task-priority-select";
import { TaskStatusSelect } from "@/components/tasks/task-status-select";
import { formatDueDate } from "@/lib/dates";
import type { TaskPriority, TaskStatus, TaskSummary, TaskUpdatePayload } from "@/lib/types";

export function TaskRow({
  task,
  onUpdate,
  onDelete,
  isDeleting,
}: {
  task: TaskSummary;
  onUpdate: (payload: TaskUpdatePayload) => void;
  onDelete: () => void;
  isDeleting: boolean;
}) {
  const [editingTitle, setEditingTitle] = useState(false);
  const [draftTitle, setDraftTitle] = useState(task.title);

  function commitTitle() {
    setEditingTitle(false);
    const trimmed = draftTitle.trim();
    if (trimmed && trimmed !== task.title) {
      onUpdate({ title: trimmed });
    } else {
      setDraftTitle(task.title);
    }
  }

  return (
    <li className="flex items-center gap-3 border-b border-border px-3 py-2.5 last:border-b-0">
      <div className="min-w-0 flex-1">
        {editingTitle ? (
          <input
            autoFocus
            value={draftTitle}
            onChange={(e) => setDraftTitle(e.target.value)}
            onBlur={commitTitle}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitTitle();
              if (e.key === "Escape") {
                setDraftTitle(task.title);
                setEditingTitle(false);
              }
            }}
            className="w-full rounded border border-accent bg-background px-1.5 py-0.5 text-sm focus:outline-none"
          />
        ) : (
          <button
            type="button"
            onClick={() => setEditingTitle(true)}
            className={
              "block truncate rounded px-1 py-0.5 text-left text-sm hover:bg-surface-2 " +
              (task.status === "done" ? "text-muted line-through" : "")
            }
            title="Click to edit"
          >
            {task.title}
          </button>
        )}
        <div className="mt-0.5 flex flex-wrap items-center gap-1.5 px-1">
          {task.source === "ai" && <AiOriginBadge />}
          {task.subtask_total > 0 && (
            <Badge>
              {task.subtask_done}/{task.subtask_total} subtasks
            </Badge>
          )}
          {task.due_date && <Badge>{formatDueDate(task.due_date)}</Badge>}
          {task.estimate_minutes != null && (
            <Badge>{Math.round(task.estimate_minutes / 60) || "<1"}h estimate</Badge>
          )}
        </div>
      </div>

      <TaskPrioritySelect
        value={task.priority}
        onChange={(priority: TaskPriority) => onUpdate({ priority })}
      />
      <TaskStatusSelect value={task.status} onChange={(status: TaskStatus) => onUpdate({ status })} />

      <button
        type="button"
        onClick={onDelete}
        disabled={isDeleting}
        aria-label={`Delete ${task.title}`}
        className="shrink-0 rounded p-1.5 text-muted hover:bg-danger/10 hover:text-danger disabled:opacity-50"
      >
        <Trash2 size={14} />
      </button>
    </li>
  );
}
