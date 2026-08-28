// Mirrors backend `RichText` (backend/app/schemas/common.py) and DESIGN.md §1a.
export type RichText = { html: string; text: string };

export const EMPTY_RICH_TEXT: RichText = { html: "", text: "" };
