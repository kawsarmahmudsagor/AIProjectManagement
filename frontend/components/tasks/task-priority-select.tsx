"use client";

import { Select } from "@/components/ui/select";
import { PRIORITY_LABELS, PRIORITY_ORDER } from "@/components/tasks/task-constants";
import type { TaskPriority } from "@/lib/types";

export function TaskPrioritySelect({
  value,
  onChange,
  disabled,
}: {
  value: TaskPriority;
  onChange: (priority: TaskPriority) => void;
  disabled?: boolean;
}) {
  return (
    <Select
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value as TaskPriority)}
      aria-label="Priority"
      className="min-w-[7rem]"
    >
      {PRIORITY_ORDER.map((p) => (
        <option key={p} value={p}>
          {PRIORITY_LABELS[p]}
        </option>
      ))}
    </Select>
  );
}
