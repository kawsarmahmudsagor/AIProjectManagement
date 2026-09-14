"use client";

import { LogOut, Palette } from "lucide-react";
import { useRouter } from "next/navigation";
import { Avatar } from "@/components/ui/avatar";
import { Menu, MenuItem } from "@/components/ui/menu";
import { ThemeToggleItems } from "@/components/layout/theme-toggle";
import { cn } from "@/lib/utils";

/** Replaces the sidebar footer's truncated-email text with a proper identity + actions
 * menu — requireSession() (lib/session.ts) already returns first_name/preferred_name, so
 * there was no reason AppShell only ever received `email`. */
export function UserMenu({
  displayName,
  email,
  collapsed,
}: {
  displayName: string;
  email: string;
  collapsed: boolean;
}) {
  const router = useRouter();

  const logout = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  };

  return (
    <Menu
      align="start"
      trigger={(triggerProps) => (
        <button
          type="button"
          {...triggerProps}
          title={collapsed ? displayName : undefined}
          className={cn(
            "flex w-full items-center gap-2 rounded-lg p-1.5 text-left hover:bg-surface-2",
            collapsed && "justify-center",
          )}
        >
          <Avatar name={displayName} />
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{displayName}</p>
              <p className="truncate text-xs text-muted">{email}</p>
            </div>
          )}
        </button>
      )}
    >
      <div className="border-b border-border px-3 py-2">
        <p className="truncate text-sm font-medium">{displayName}</p>
        <p className="truncate text-xs text-muted">{email}</p>
      </div>
      <div className="border-b border-border py-1">
        <p className="flex items-center gap-2 px-3 py-1 text-xs font-medium text-muted">
          <Palette size={12} /> Theme
        </p>
        <ThemeToggleItems />
      </div>
      <div className="py-1">
        <MenuItem onClick={() => void logout()} className="text-danger">
          <LogOut size={14} /> Log out
        </MenuItem>
      </div>
    </Menu>
  );
}
