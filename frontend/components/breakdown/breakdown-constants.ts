import type { EstimateSize } from "@/lib/types";

export const BREAKDOWN_STAGE_ORDER = ["queued", "parsing", "extracting", "structuring"] as const;

export const BREAKDOWN_STAGE_LABELS: Record<(typeof BREAKDOWN_STAGE_ORDER)[number], string> = {
  queued: "Queued",
  parsing: "Reading document",
  extracting: "Planning the work",
  structuring: "Organizing tasks",
};

export function breakdownStageLabel(status: string | undefined): string {
  if (status && (BREAKDOWN_STAGE_ORDER as readonly string[]).includes(status)) {
    return BREAKDOWN_STAGE_LABELS[status as (typeof BREAKDOWN_STAGE_ORDER)[number]];
  }
  return "Working…";
}

// Mirrors backend/app/core/config.py's BREAKDOWN_ESTIMATE_SIZE_MINUTES — used only to
// prefill each review row's editable hours input. Display-only: the backend re-derives
// the same default itself from estimate_size if a row's estimate_minutes is left as-is,
// so this copy is never the only source of truth.
export const ESTIMATE_SIZE_MINUTES: Record<EstimateSize, number> = {
  xs: 30,
  s: 120,
  m: 240,
  l: 480,
  xl: 960,
};

export const ESTIMATE_SIZE_ORDER: EstimateSize[] = ["xs", "s", "m", "l", "xl"];

export const ESTIMATE_SIZE_LABELS: Record<EstimateSize, string> = {
  xs: "XS",
  s: "S",
  m: "M",
  l: "L",
  xl: "XL",
};

export function minutesToHoursLabel(minutes: number | null): string {
  if (minutes === null) return "—";
  const hours = minutes / 60;
  return hours === Math.floor(hours) ? `${hours}h` : `${hours.toFixed(1)}h`;
}
