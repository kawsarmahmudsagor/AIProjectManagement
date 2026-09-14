"use client";

import { usePathname } from "next/navigation";
import { Tabs } from "@/components/ui/tabs";

const TAB_HREFS = [
  { href: "/settings/ai-providers", label: "AI Providers" },
  { href: "/settings/chatbot", label: "Chatbot" },
];

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold">Settings</h1>
      <Tabs
        className="mb-6"
        tabs={TAB_HREFS.map((tab) => ({ ...tab, active: pathname.startsWith(tab.href) }))}
      />
      {children}
    </div>
  );
}
