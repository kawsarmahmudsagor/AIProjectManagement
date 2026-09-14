import { apiFetch } from "@/lib/api-client";
import type { DashboardSummary } from "@/lib/types";

/** Thin client-side accessor — the dashboard page itself uses serverApiFetch directly
 * (matching every other page in app/(app)/), this is here for any client-side refetch
 * (e.g. after a project's technologies change and the skills chips should update). */
export async function getDashboardSummary(): Promise<DashboardSummary> {
  return apiFetch<DashboardSummary>("dashboard/summary");
}
