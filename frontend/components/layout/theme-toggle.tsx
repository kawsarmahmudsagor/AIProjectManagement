"use client";

import { Check, Monitor, Moon, Sun } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { MenuItem } from "@/components/ui/menu";
import { parseThemeCookie, themeDataAttr, THEME_COOKIE, type ThemeChoice } from "@/lib/theme";

function readThemeCookie(): ThemeChoice {
  if (typeof document === "undefined") return "system";
  const match = document.cookie.match(new RegExp(`(?:^|; )${THEME_COOKIE}=([^;]*)`));
  return parseThemeCookie(match ? decodeURIComponent(match[1]) : undefined);
}

const OPTIONS: { value: ThemeChoice; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

/** The three MenuItem rows for the sidebar's user menu. Applies the choice optimistically
 * to `document.documentElement` (instant, no flash while the request is in flight) then
 * persists it via POST /api/theme and refreshes so every server-rendered page (including
 * ones the app navigates to next) picks up the new cookie on its next request — see
 * app/layout.tsx's server-side read and lib/theme.ts's docstring on why a cookie beats a
 * blocking inline script here. */
export function ThemeToggleItems() {
  const router = useRouter();
  const [choice, setChoice] = useState<ThemeChoice>(readThemeCookie);

  const apply = async (next: ThemeChoice) => {
    setChoice(next);
    const attr = themeDataAttr(next);
    if (attr) document.documentElement.setAttribute("data-theme", attr);
    else document.documentElement.removeAttribute("data-theme");

    await fetch("/api/theme", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme: next }),
    }).catch(() => {
      // Best effort — the optimistic DOM update above already reflects the choice for
      // this tab; a failed persist just means it won't survive a fresh server render.
    });
    router.refresh();
  };

  return (
    <>
      {OPTIONS.map((opt) => (
        <MenuItem key={opt.value} onClick={() => void apply(opt.value)}>
          <opt.icon size={14} className="shrink-0" />
          <span className="flex-1">{opt.label}</span>
          {choice === opt.value && <Check size={14} className="shrink-0 text-accent" />}
        </MenuItem>
      ))}
    </>
  );
}
