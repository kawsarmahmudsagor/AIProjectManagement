"use client";

import { Star } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError } from "@/lib/api-client";
import { setSessionStarred } from "@/lib/chat";
import { cn } from "@/lib/utils";

export function StarToggleButton({ sessionId, starred }: { sessionId: string; starred: boolean }) {
  const router = useRouter();
  const [isSaving, setIsSaving] = useState(false);

  async function handleClick() {
    setIsSaving(true);
    try {
      await setSessionStarred(sessionId, !starred);
      router.refresh();
    } catch (err) {
      // Best-effort — a failed star toggle just leaves the row as it was.
      if (err instanceof ApiError) console.error(err.message);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
    >
      <button
        type="button"
        onClick={handleClick}
        disabled={isSaving}
        aria-pressed={starred}
        aria-label={starred ? "Unstar conversation" : "Star conversation"}
        className="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-foreground disabled:opacity-60"
      >
        <Star size={16} className={cn(starred && "fill-amber-400 text-amber-400")} />
      </button>
    </div>
  );
}
