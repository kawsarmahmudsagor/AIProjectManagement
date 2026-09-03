import { differenceInCalendarDays, format, isBefore, isValid, parseISO, startOfToday } from "date-fns";

/** The single entry point for date formatting in this app. date-fns was already a
 * dependency, imported nowhere — every date display before this used its own hand-rolled
 * `toLocaleDateString` call. Using date-fns only for new (task) call sites while leaving
 * the existing ones hand-rolled would be worse than either extreme, so the three
 * pre-existing call sites (project-card.tsx, projects/[projectId]/page.tsx,
 * conversation-list.tsx) were migrated to this module in the same change. */

function toDate(iso: string): Date {
  return parseISO(iso);
}

export function formatMonthYear(iso: string): string {
  const d = toDate(iso);
  return isValid(d) ? format(d, "MMM yyyy") : "";
}

export function formatLongMonthYear(iso: string): string {
  const d = toDate(iso);
  return isValid(d) ? format(d, "MMMM yyyy") : "";
}

export function formatTimestamp(iso: string): string {
  const d = toDate(iso);
  return isValid(d) ? format(d, "MMM d, yyyy h:mm a") : "";
}

export function formatDay(iso: string): string {
  const d = toDate(iso);
  return isValid(d) ? format(d, "MMM d") : "";
}

export function isOverdue(iso: string): boolean {
  const d = toDate(iso);
  return isValid(d) && isBefore(d, startOfToday());
}

/** "Overdue", "Today", "Tomorrow", or a short date — used on task due-date badges. */
export function formatDueDate(iso: string): string {
  const d = toDate(iso);
  if (!isValid(d)) return "";
  const days = differenceInCalendarDays(d, startOfToday());
  if (days < 0) return "Overdue";
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  return formatDay(iso);
}
