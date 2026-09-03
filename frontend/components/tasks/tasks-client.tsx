"use client";

import { ListChecks, Sparkles } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { STATUS_LABELS, STATUS_ORDER } from "@/components/tasks/task-constants";
import { TaskCreateRow } from "@/components/tasks/task-create-row";
import { TaskRow } from "@/components/tasks/task-row";
import { useCreateTask, useDeleteTask, useProjectTasks, useUpdateTask } from "@/hooks/use-tasks";
import type { TaskListResponse, TaskStatus, TaskUpdatePayload } from "@/lib/types";

export function TasksClient({
  projectId,
  initialData,
}: {
  projectId: string;
  initialData: TaskListResponse;
}) {
  const { data } = useProjectTasks(projectId, { sort: "board" }, initialData);
  const createTask = useCreateTask(projectId);
  const updateTask = useUpdateTask(projectId);
  const deleteTask = useDeleteTask(projectId);

  const items = data?.items ?? [];

  const breakdownLink = (
    <Link href={`/projects/${projectId}/tasks/breakdown`}>
      <Button type="button" variant="secondary">
        <Sparkles size={14} /> Break down a document
      </Button>
    </Link>
  );

  if (items.length === 0 && !createTask.isPending) {
    return (
      <>
        <EmptyState
          icon={<ListChecks size={28} />}
          title="No tasks yet"
          description="Add one by hand below, or upload a spec and let the AI propose a task list to review."
          action={breakdownLink}
        />
        <div className="mt-4">
          <TaskCreateRow
            onCreate={(title) => createTask.mutate({ title })}
            isCreating={createTask.isPending}
          />
        </div>
      </>
    );
  }

  const byStatus = new Map<TaskStatus, typeof items>();
  for (const status of STATUS_ORDER) byStatus.set(status, []);
  for (const task of items) {
    if (task.parent_id) continue; // top-level only in this view
    byStatus.get(task.status)?.push(task);
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-end">{breakdownLink}</div>

      {STATUS_ORDER.map((status) => {
        const tasksInColumn = byStatus.get(status) ?? [];
        if (tasksInColumn.length === 0) return null;
        return (
          <div key={status}>
            <h2 className="mb-2 text-sm font-medium text-muted">
              {STATUS_LABELS[status]} · {tasksInColumn.length}
            </h2>
            <ul className="overflow-hidden rounded-xl border border-border">
              {tasksInColumn.map((task) => (
                <TaskRow
                  key={task.id}
                  task={task}
                  onUpdate={(payload: TaskUpdatePayload) =>
                    updateTask.mutate({ taskId: task.id, payload })
                  }
                  onDelete={() => deleteTask.mutate(task.id)}
                  isDeleting={deleteTask.isPending && deleteTask.variables === task.id}
                />
              ))}
            </ul>
          </div>
        );
      })}

      <TaskCreateRow
        onCreate={(title) => createTask.mutate({ title })}
        isCreating={createTask.isPending}
      />
    </div>
  );
}
