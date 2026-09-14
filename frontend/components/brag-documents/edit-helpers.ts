import type { BragDocumentResult } from "@/lib/types";

/** Pure, immutable update helpers for the brag document editor — each returns a new
 * BragDocumentResult with exactly one change applied, so every edit/removal in
 * brag-document-result.tsx is a single `setResult(fn(result))` call. No lens/optics
 * library here since the nesting is only two levels deep (group -> subsection -> bullet)
 * and there are few enough call sites that writing them out plainly stays easy to read.
 */

export function setGroupField(
  result: BragDocumentResult,
  groupIdx: number,
  field: "project_name" | "key_contribution",
  value: string,
): BragDocumentResult {
  return {
    ...result,
    technical_contributions: result.technical_contributions.map((g, i) =>
      i === groupIdx ? { ...g, [field]: value } : g,
    ),
  };
}

export function removeGroup(result: BragDocumentResult, groupIdx: number): BragDocumentResult {
  return {
    ...result,
    technical_contributions: result.technical_contributions.filter((_, i) => i !== groupIdx),
  };
}

export function setGroupBullet(
  result: BragDocumentResult,
  groupIdx: number,
  bulletIdx: number,
  value: string,
): BragDocumentResult {
  return {
    ...result,
    technical_contributions: result.technical_contributions.map((g, i) =>
      i === groupIdx ? { ...g, bullets: g.bullets.map((b, j) => (j === bulletIdx ? value : b)) } : g,
    ),
  };
}

export function setSubsectionHeading(
  result: BragDocumentResult,
  groupIdx: number,
  subIdx: number,
  value: string,
): BragDocumentResult {
  return {
    ...result,
    technical_contributions: result.technical_contributions.map((g, i) =>
      i === groupIdx
        ? { ...g, subsections: g.subsections.map((s, k) => (k === subIdx ? { ...s, heading: value } : s)) }
        : g,
    ),
  };
}

export function removeSubsection(result: BragDocumentResult, groupIdx: number, subIdx: number): BragDocumentResult {
  return {
    ...result,
    technical_contributions: result.technical_contributions.map((g, i) =>
      i === groupIdx ? { ...g, subsections: g.subsections.filter((_, k) => k !== subIdx) } : g,
    ),
  };
}

export function setSubsectionBullet(
  result: BragDocumentResult,
  groupIdx: number,
  subIdx: number,
  bulletIdx: number,
  value: string,
): BragDocumentResult {
  return {
    ...result,
    technical_contributions: result.technical_contributions.map((g, i) =>
      i === groupIdx
        ? {
            ...g,
            subsections: g.subsections.map((s, k) =>
              k === subIdx ? { ...s, bullets: s.bullets.map((b, j) => (j === bulletIdx ? value : b)) } : s,
            ),
          }
        : g,
    ),
  };
}

type FlatBulletKey = "team_support_bullets" | "learning_bullets";

export function setFlatBullet(
  result: BragDocumentResult,
  key: FlatBulletKey,
  idx: number,
  value: string,
): BragDocumentResult {
  return { ...result, [key]: result[key].map((b, i) => (i === idx ? value : b)) };
}

export function removeFlatBullet(result: BragDocumentResult, key: FlatBulletKey, idx: number): BragDocumentResult {
  return { ...result, [key]: result[key].filter((_, i) => i !== idx) };
}

export function setImpactField(
  result: BragDocumentResult,
  idx: number,
  field: "category" | "summary",
  value: string,
): BragDocumentResult {
  return {
    ...result,
    overall_impact: result.overall_impact.map((a, i) => (i === idx ? { ...a, [field]: value } : a)),
  };
}

export function removeImpactArea(result: BragDocumentResult, idx: number): BragDocumentResult {
  return { ...result, overall_impact: result.overall_impact.filter((_, i) => i !== idx) };
}
