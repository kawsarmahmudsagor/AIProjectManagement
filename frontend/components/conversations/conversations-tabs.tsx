"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { Tabs } from "@/components/ui/tabs";

const TAB_VALUES = [
  { value: "conversations", label: "Conversations" },
  { value: "suggestions", label: "Suggestions" },
] as const;

export function ConversationsTabs() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const active = searchParams.get("tab") === "suggestions" ? "suggestions" : "conversations";

  return (
    <Tabs
      tabs={TAB_VALUES.map((tab) => ({
        href: tab.value === "conversations" ? pathname : `${pathname}?tab=${tab.value}`,
        label: tab.label,
        active: active === tab.value,
      }))}
    />
  );
}
