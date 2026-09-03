"use client";

import { Plus } from "lucide-react";
import { useState } from "react";
import { Input } from "@/components/ui/input";

export function TaskCreateRow({
  onCreate,
  isCreating,
}: {
  onCreate: (title: string) => void;
  isCreating: boolean;
}) {
  const [title, setTitle] = useState("");

  function submit() {
    const trimmed = title.trim();
    if (!trimmed || isCreating) return;
    onCreate(trimmed);
    setTitle("");
  }

  return (
    <div className="flex items-center gap-2 rounded-xl border border-dashed border-border px-3 py-2">
      <Plus size={16} className="shrink-0 text-muted" />
      <Input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") submit();
        }}
        placeholder="Add a task…"
        disabled={isCreating}
        className="border-none bg-transparent px-0 py-1 focus:ring-0"
      />
    </div>
  );
}
