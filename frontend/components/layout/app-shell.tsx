"use client";

import { ChevronLeft, FileBadge, LayoutDashboard, MessagesSquare, Settings, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { ChatWidget } from "@/components/chat/chat-widget";
import { ChatWidgetProvider, useChatWidget } from "@/components/chat/chat-widget-context";
import { ProjectsNavSection } from "@/components/layout/projects-nav-section";
import { UserMenu } from "@/components/layout/user-menu";
import { usePersistedCollapse } from "@/hooks/use-persisted-collapse";
import { cn } from "@/lib/utils";

// Grouped rather than one flat list — a light section label (shown only when expanded)
// so related items (the assistant-adjacent features vs. the core workspace) read as
// intentionally clustered rather than an arbitrary stack. Every href here is a route
// that actually exists today — no placeholder links to routes this app doesn't have.
const NAV_GROUPS: { label: string; items: { href: string; label: string; icon: typeof LayoutDashboard }[] }[] = [
  {
    label: "Workspace",
    items: [{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard }],
  },
  {
    label: "Assistant",
    items: [
      { href: "/conversations", label: "Conversations", icon: MessagesSquare },
      { href: "/brag-documents", label: "Brag Documents", icon: FileBadge },
    ],
  },
];
const NAV_BOTTOM = [
  { href: "/profile", label: "Profile", icon: UserRound },
  { href: "/settings/ai-providers", label: "Settings", icon: Settings },
];

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

export function AppShell({
  displayName,
  email,
  children,
}: {
  displayName: string;
  email: string;
  children: React.ReactNode;
}) {
  return (
    <ChatWidgetProvider>
      <AppShellContent displayName={displayName} email={email}>
        {children}
      </AppShellContent>
    </ChatWidgetProvider>
  );
}

function AppShellContent({
  displayName,
  email,
  children,
}: {
  displayName: string;
  email: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = usePersistedCollapse();
  const { isOpen, width, presentation } = useChatWidget();
  // 0 whenever the panel isn't actually occupying flex-layout width (closed, or in the
  // overlay/fullscreen presentations, both already position:fixed with no need for the
  // toast to dodge them the same way).
  const chatInset = isOpen && presentation === "docked" ? width : 0;

  // Set on <html>, not this component's own root div: components/ui/toaster.tsx's toast
  // container is a DOM *sibling* of AppShell's tree (both live inside app/providers.tsx's
  // ToasterProvider, which renders `{children}` and its own toast div as siblings), not
  // a descendant of it — a CSS custom property only inherits down from a true ancestor,
  // so setting it on this div would never actually reach the toast container. <html> is
  // a genuine ancestor of both.
  useEffect(() => {
    document.documentElement.style.setProperty("--chat-inset", `${chatInset}px`);
    return () => {
      document.documentElement.style.removeProperty("--chat-inset");
    };
  }, [chatInset]);

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
        <nav className="flex-1 space-y-4 overflow-y-auto">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="space-y-1">
              {!collapsed && (
                <p className="px-3 text-2xs font-semibold uppercase tracking-wide text-muted">{group.label}</p>
              )}
              {group.items.map((item) => (
                <NavLink key={item.href} {...item} active={pathname.startsWith(item.href)} collapsed={collapsed} />
              ))}
            </div>
          ))}
          <div className="space-y-1">
            {!collapsed && <p className="px-3 text-2xs font-semibold uppercase tracking-wide text-muted">Projects</p>}
            <ProjectsNavSection collapsed={collapsed} />
          </div>
        </nav>
        <div className="space-y-1 border-t border-border pt-3">
          {NAV_BOTTOM.map((item) => (
            <NavLink key={item.href} {...item} active={pathname.startsWith(item.href)} collapsed={collapsed} />
          ))}
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            className="flex w-full items-center justify-center rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-foreground"
          >
            <ChevronLeft size={16} className={cn("transition-transform", collapsed && "rotate-180")} />
          </button>
          <UserMenu displayName={displayName} email={email} collapsed={collapsed} />
        </div>
      </aside>
      {/* @container + min-w-0 unblock the chat dock (Part 6 of the plan): min-w-0 is
          required so this flex item can actually shrink when the dock claims width
          instead of pushing it off-screen (a flex item defaults to min-width:auto),
          and @container lets in-page grids react to *this* element's width via @lg:/
          @4xl: variants rather than the viewport's — verified against the installed
          Tailwind v4 engine (container-type: inline-size + `@container (width >= ...)`
          media queries), not assumed from training data per frontend/AGENTS.md. */}
      <main className="@container min-w-0 flex-1 p-8">{children}</main>
      <ChatWidget />
    </div>
  );
}
