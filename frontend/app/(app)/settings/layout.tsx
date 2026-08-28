"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/settings/ai-providers", label: "AI Providers" },
  { href: "/settings/chatbot", label: "Chatbot" },
];

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold">Settings</h1>
      <div className="mb-6 flex gap-4 border-b border-border text-sm">
        {TABS.map((tab) => (
          <Link
            key={tab.href}
            href={tab.href}
            className={cn(
              "border-b-2 px-1 pb-2",
              pathname.startsWith(tab.href) ? "border-accent text-foreground" : "border-transparent text-muted hover:text-foreground",
            )}
          >
            {tab.label}
          </Link>
        ))}
      </div>
      {children}
    </div>
  );
}
