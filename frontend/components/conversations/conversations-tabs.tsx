"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";

const TABS = [
  { value: "conversations", label: "Conversations" },
  { value: "suggestions", label: "Suggestions" },
] as const;

export function ConversationsTabs() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const active = searchParams.get("tab") === "suggestions" ? "suggestions" : "conversations";

  return (
    <div className="flex items-center gap-1 border-b border-border">
      {TABS.map((tab) => (
        <button
          key={tab.value}
          type="button"
          onClick={() => router.push(tab.value === "conversations" ? pathname : `${pathname}?tab=${tab.value}`)}
          aria-current={active === tab.value ? "page" : undefined}
          className={cn(
            "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
            active === tab.value
              ? "border-accent text-foreground"
              : "border-transparent text-muted hover:text-foreground",
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
