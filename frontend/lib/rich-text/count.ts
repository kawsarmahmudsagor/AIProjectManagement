// Grapheme-aware count so emoji/combining marks count as 1 character, matching what a
// human reading a "390/390" counter would expect (DESIGN.md §1a).
const segmenter = typeof Intl !== "undefined" && "Segmenter" in Intl ? new Intl.Segmenter(undefined, { granularity: "grapheme" }) : null;

export function countPlain(text: string): number {
  if (!text) return 0;
  if (!segmenter) return text.length;
  return [...segmenter.segment(text)].length;
}
