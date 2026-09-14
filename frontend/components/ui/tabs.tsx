import Link from "next/link";
import { cn } from "@/lib/utils";

/** Consolidates two near-identical hand-rolled tab bars
 * (app/(app)/settings/layout.tsx's inline version and
 * components/conversations/conversations-tabs.tsx) into one primitive. Deliberately
 * link-based (not button-based with client state) — both existing call sites drive the
 * active tab from the URL (a route segment or a `?tab=` param), which is what makes
 * "share this URL" and "the browser back button" work; a component that instead took an
 * internal `value`/`onChange` would have to be reconciled with the URL by its caller
 * anyway. Callers that need query-param tabs pass `href` built from `usePathname()` +
 * `useSearchParams()` themselves (see conversations-tabs.tsx for the pattern) — this
 * component only renders and styles. */
export function Tabs({
  tabs,
  className,
}: {
  tabs: { href: string; label: string; active: boolean }[];
  className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-1 border-b border-border", className)} role="tablist">
      {tabs.map((tab) => (
        <Link
          key={tab.href}
          href={tab.href}
          role="tab"
          aria-selected={tab.active}
          className={cn(
            "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
            tab.active
              ? "border-accent text-foreground"
              : "border-transparent text-muted hover:text-foreground",
          )}
        >
          {tab.label}
        </Link>
      ))}
    </div>
  );
}
