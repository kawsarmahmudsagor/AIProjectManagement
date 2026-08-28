"use client";

import { ChevronLeft, LayoutDashboard, Settings, LogOut, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useState } from "react";
import { ChatWidget } from "@/components/chat/chat-widget";
import { ProjectsNavSection } from "@/components/layout/projects-nav-section";
import { cn } from "@/lib/utils";

const NAV_TOP = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/profile", label: "Profile", icon: UserRound },
];
const NAV_BOTTOM = [{ href: "/settings/ai-providers", label: "Settings", icon: Settings }];

function NavLink({
  href,
  label,
  icon: Icon,
  active,
  collapsed,
}: {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  active: boolean;
  collapsed: boolean;
}) {
  return (
    <Link
      href={href}
      title={collapsed ? label : undefined}
      className={cn(
        "flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted hover:bg-surface-2 hover:text-foreground",
        collapsed && "justify-center px-2",
        active && "bg-surface-2 text-foreground",
      )}
    >
      <Icon size={16} />
      {!collapsed && label}
    </Link>
  );
}

export function AppShell({ email, children }: { email: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);

  const logout = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  };

  return (
    <div className="flex min-h-screen">
      <aside
        className={cn(
          "sticky top-0 flex h-screen shrink-0 flex-col border-r border-border bg-surface p-4 transition-[width] duration-200",
          collapsed ? "w-16" : "w-60",
        )}
      >
        <div className={cn("mb-8 flex items-center", collapsed ? "justify-center" : "px-2")}>
          {!collapsed && <span className="text-sm font-semibold">AI Project Management</span>}
        </div>
        <nav className="flex-1 space-y-1">
          {NAV_TOP.map((item) => (
            <NavLink key={item.href} {...item} active={pathname.startsWith(item.href)} collapsed={collapsed} />
          ))}
          <ProjectsNavSection collapsed={collapsed} />
          {NAV_BOTTOM.map((item) => (
            <NavLink key={item.href} {...item} active={pathname.startsWith(item.href)} collapsed={collapsed} />
          ))}
        </nav>
        <div className="border-t border-border pt-3">
          <button
            type="button"
            onClick={() => setCollapsed((v) => !v)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            className="flex w-full items-center justify-center rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-foreground"
          >
            <ChevronLeft size={16} className={cn("transition-transform", collapsed && "rotate-180")} />
          </button>
          {!collapsed && <p className="mt-1 truncate px-2 text-center text-xs text-muted">{email}</p>}
          <button
            onClick={logout}
            title="Log out"
            aria-label="Log out"
            className="mt-1 flex w-full items-center justify-center rounded-lg px-2 py-2 text-sm text-muted hover:bg-surface-2 hover:text-foreground"
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>
      <main className="flex-1 p-8">{children}</main>
      <ChatWidget />
    </div>
  );
}
