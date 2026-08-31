"use client";

import { Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useDebouncedCallback } from "@/hooks/use-debounced-callback";

export function ConversationSearch() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [value, setValue] = useState(searchParams.get("q") ?? "");

  const { run: push } = useDebouncedCallback((q: string) => {
    const params = new URLSearchParams(searchParams);
    if (q) params.set("q", q);
    else params.delete("q");
    router.replace(`${pathname}?${params.toString()}`);
  }, 300);

  return (
    <div className="relative w-72">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} />
      <input
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          push(e.target.value);
        }}
        placeholder="Search conversations..."
        className="w-full rounded-lg border border-border bg-background py-2 pl-9 pr-3 text-sm placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/50"
      />
    </div>
  );
}
