"use client";

import { Select } from "@/components/ui/select";
import { STATUS_LABELS, STATUS_ORDER } from "@/components/tasks/task-constants";
import type { TaskStatus } from "@/lib/types";

export function TaskStatusSelect({
  value,
  onChange,
  disabled,
}: {
  value: TaskStatus;
  onChange: (status: TaskStatus) => void;
  disabled?: boolean;
}) {
  return (
    <Select
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value as TaskStatus)}
      aria-label="Status"
      className="min-w-[9.5rem]"
    >
      {STATUS_ORDER.map((s) => (
        <option key={s} value={s}>
          {STATUS_LABELS[s]}
        </option>
      ))}
    </Select>
  );
}
