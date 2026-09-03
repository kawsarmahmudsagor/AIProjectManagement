export const BRAG_DOCUMENT_STAGE_ORDER = ["queued", "parsing", "extracting", "structuring"] as const;

export const BRAG_DOCUMENT_STAGE_LABELS: Record<(typeof BRAG_DOCUMENT_STAGE_ORDER)[number], string> = {
  queued: "Queued",
  parsing: "Reading spreadsheet",
  extracting: "Gathering project context & drafting",
  structuring: "Finalizing document",
};

export function bragDocumentStageLabel(status: string | undefined): string {
  if (status && (BRAG_DOCUMENT_STAGE_ORDER as readonly string[]).includes(status)) {
    return BRAG_DOCUMENT_STAGE_LABELS[status as (typeof BRAG_DOCUMENT_STAGE_ORDER)[number]];
  }
  return "Working…";
}
