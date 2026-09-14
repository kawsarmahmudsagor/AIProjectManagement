import { cn } from "@/lib/utils";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Initials-only for now — no photo support (the app has no per-user avatar image
 * concept, distinct from the Profile page's own photo used only there). Replaces the
 * truncated-email footer text in the sidebar with something that reads as identity at a
 * glance even when the sidebar is collapsed to icon width. */
export function Avatar({ name, className }: { name: string; className?: string }) {
  return (
    <div
      className={cn(
        "flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-subtle text-xs font-semibold text-accent-solid",
        className,
      )}
      aria-hidden="true"
    >
      {initials(name)}
    </div>
  );
}
