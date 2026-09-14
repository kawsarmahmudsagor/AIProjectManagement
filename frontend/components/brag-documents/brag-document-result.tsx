"use client";

import { Copy, Download, FileText, RotateCcw } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EditableLine, EditableParagraph } from "@/components/brag-documents/editable-field";
import {
  removeFlatBullet,
  removeGroup,
  removeImpactArea,
  removeSubsection,
  setFlatBullet,
  setGroupBullet,
  setGroupField,
  setImpactField,
  setSubsectionBullet,
  setSubsectionHeading,
} from "@/components/brag-documents/edit-helpers";
import { RemoveIconButton } from "@/components/brag-documents/remove-icon-button";
import { useResetBragDocumentEdits, useUpdateBragDocumentResult } from "@/hooks/use-brag-document-job";
import type {
  BragDocumentJob,
  BragDocumentResult as BragDocumentResultData,
  BragDocumentTechnicalContributionGroup,
} from "@/lib/types";

function bulletsToText(bullets: string[]): string {
  return bullets.map((b) => `- ${b}`).join("\n");
}

function sectionText(title: string, bullets: string[]): string {
  return `${title}\n${bulletsToText(bullets)}`;
}

function groupText(group: BragDocumentTechnicalContributionGroup): string {
  const parts: string[] = [group.project_name];
  for (const sub of group.subsections) {
    parts.push(`  ${sub.heading}`);
    parts.push(bulletsToText(sub.bullets).replace(/^/gm, "  "));
  }
  if (group.bullets.length > 0) {
    parts.push(bulletsToText(group.bullets));
  }
  if (group.key_contribution) {
    parts.push(`Key Contribution: ${group.key_contribution}`);
  }
  return parts.join("\n");
}

function buildFullDocumentText(job: BragDocumentJob, result: BragDocumentResultData): string {
  const parts: string[] = [`Brag Document — ${job.member_name} — ${job.target_month}`, ""];

  if (result.technical_contributions.length > 0) {
    parts.push("Technical Contribution");
    for (const group of result.technical_contributions) {
      parts.push(groupText(group));
      parts.push("");
    }
  }

  if (result.overall_impact.length > 0) {
    parts.push("Overall Impact");
    parts.push(bulletsToText(result.overall_impact.map((a) => `${a.category}: ${a.summary}`)));
    parts.push("");
  }

  parts.push(sectionText("Team Support & Collaboration", result.team_support_bullets), "");
  parts.push(sectionText("Learning & Development", result.learning_bullets));

  return parts.join("\n").trim();
}

function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      type="button"
      variant="ghost"
      className="h-7 shrink-0 px-2 text-xs"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      <Copy size={13} /> {copied ? "Copied" : label}
    </Button>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-2/30 px-3 py-2">
      <p className="text-xs text-muted">{label}</p>
      <p className="text-sm font-medium">{value}</p>
    </div>
  );
}

function HourStatsCard({ job }: { job: BragDocumentJob }) {
  const stats = job.hour_stats;
  if (!stats) return null;

  return (
    <Card className="space-y-3">
      <div>
        <h2 className="font-medium">{stats.month_name} {stats.year}</h2>
        <p className="text-sm text-muted">{stats.member_name}</p>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <StatTile label="Total hours" value={stats.total_hours.toFixed(1)} />
        <StatTile label="Target hours" value={stats.expected_target_hours.toFixed(1)} />
        <StatTile
          label="Balance"
          value={`${stats.balance_hours >= 0 ? "+" : ""}${stats.balance_hours.toFixed(1)}`}
        />
        <StatTile label="Completion" value={`${stats.target_completion_pct.toFixed(0)}%`} />
        <StatTile label="Billable" value={stats.billable_hours.toFixed(1)} />
        <StatTile label="Non-billable" value={stats.non_billable_hours.toFixed(1)} />
        <StatTile
          label="Holidays"
          value={stats.holiday_count > 0 ? `${stats.holiday_count} (${stats.holiday_names.join(", ")})` : "0"}
        />
        <StatTile label="Leave" value={stats.leave_count > 0 ? `${stats.leave_count} day${stats.leave_count === 1 ? "" : "s"}` : "0"} />
      </div>
      {stats.included_weeks.length > 0 && (
        <p className="text-xs text-muted">Weeks included: {stats.included_weeks.join(", ")}</p>
      )}
    </Card>
  );
}

/** A list of bullet lines, editable text plus an optional per-line remove button.
 * `onRemove` is only passed for the flat top-level sections (Team Support, Learning),
 * where one bullet line *is* the removable unit — omitted for bullets nested inside a
 * Technical Contribution project group or sub-theme, where the group/sub-theme itself
 * is the removable "tile" instead (see RemoveIconButton's other call sites below), not
 * its individual bullets. */
function EditableBulletList({
  bullets,
  itemLabel,
  onEdit,
  onRemove,
}: {
  bullets: string[];
  itemLabel?: string;
  onEdit: (idx: number, value: string) => void;
  onRemove?: (idx: number) => void;
}) {
  if (bullets.length === 0) {
    return <p className="text-sm text-muted">Nothing drafted for this section.</p>;
  }
  return (
    <ul className="space-y-1">
      {bullets.map((bullet, i) => (
        <li key={i} className="flex items-start gap-1 before:mt-2.5 before:size-1 before:shrink-0 before:rounded-full before:bg-muted">
          <EditableParagraph value={bullet} onCommit={(v) => onEdit(i, v)} className="flex-1" />
          {onRemove && <RemoveIconButton label={itemLabel ?? "this bullet"} onConfirm={() => onRemove(i)} />}
        </li>
      ))}
    </ul>
  );
}

export function BragDocumentResult({ job }: { job: BragDocumentJob }) {
  const [result, setResult] = useState(job.result);
  // Render-phase resync, only when switching to a different document (same "adjusting
  // state when a prop changes" technique as ConfirmPopover's prevOpen, and
  // EditableLine/EditableParagraph's prevValue) — keyed on job.id specifically, not
  // job.result, since our own edits already keep local state and the server in
  // agreement and re-syncing on every job.result change would risk clobbering an
  // in-progress edit with a stale round-trip response.
  const [prevJobId, setPrevJobId] = useState(job.id);
  if (prevJobId !== job.id) {
    setPrevJobId(job.id);
    setResult(job.result);
  }

  const updateMutation = useUpdateBragDocumentResult(job.id);
  const resetMutation = useResetBragDocumentEdits(job.id);

  function persist(next: BragDocumentResultData) {
    setResult(next);
    updateMutation.mutate(next);
  }

  if (!result) {
    return <p className="text-sm text-muted">This job succeeded but has no result to show.</p>;
  }

  const fullText = buildFullDocumentText(job, result);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">
            {job.member_name} — {job.target_month}
          </h1>
          <p className="text-sm text-muted">
            Edit any text below. Remove a whole project, sub-theme, or impact area, or an
            individual Team Support / Learning bullet — changes save automatically.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {updateMutation.isPending && <span className="text-xs text-muted">Saving…</span>}
          {job.is_edited && (
            <Button
              type="button"
              variant="ghost"
              className="h-8 px-2 text-xs"
              disabled={resetMutation.isPending}
              onClick={() =>
                resetMutation.mutate(undefined, { onSuccess: (fresh) => setResult(fresh.result) })
              }
            >
              <RotateCcw size={13} /> {resetMutation.isPending ? "Resetting…" : "Reset changes"}
            </Button>
          )}
          <CopyButton text={fullText} label="Copy All" />
        </div>
      </div>

      <HourStatsCard job={job} />

      {result.confidence_notes.length > 0 && (
        <ul className="space-y-1 rounded-lg border border-border bg-surface-2/30 px-3 py-2 text-xs text-muted">
          {result.confidence_notes.map((note, i) => (
            <li key={i}>{note}</li>
          ))}
        </ul>
      )}

      <Card className="space-y-3">
        <h2 className="font-medium">Technical Contribution</h2>
        {result.technical_contributions.length === 0 && (
          <p className="text-sm text-muted">No technical contributions were drafted.</p>
        )}
        {result.technical_contributions.map((group, groupIdx) => (
          <div key={groupIdx} className="space-y-2 rounded-lg border border-border p-3">
            <div className="flex items-center justify-between gap-3">
              <EditableLine
                value={group.project_name}
                onCommit={(v) => persist(setGroupField(result, groupIdx, "project_name", v))}
                className="font-medium"
              />
              <div className="flex shrink-0 items-center gap-1">
                <CopyButton text={groupText(group)} />
                <RemoveIconButton
                  label={`the "${group.project_name || "untitled"}" project group`}
                  onConfirm={() => persist(removeGroup(result, groupIdx))}
                />
              </div>
            </div>
            {group.subsections.map((sub, subIdx) => (
              <div key={subIdx} className="space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <EditableLine
                    value={sub.heading}
                    onCommit={(v) => persist(setSubsectionHeading(result, groupIdx, subIdx, v))}
                    className="text-xs font-medium text-muted"
                  />
                  <RemoveIconButton
                    label={`the "${sub.heading || "untitled"}" sub-theme`}
                    onConfirm={() => persist(removeSubsection(result, groupIdx, subIdx))}
                  />
                </div>
                <div className="pl-5">
                  <EditableBulletList
                    bullets={sub.bullets}
                    onEdit={(i, v) => persist(setSubsectionBullet(result, groupIdx, subIdx, i, v))}
                  />
                </div>
              </div>
            ))}
            {group.bullets.length > 0 && (
              <div className="pl-5">
                <EditableBulletList
                  bullets={group.bullets}
                  onEdit={(i, v) => persist(setGroupBullet(result, groupIdx, i, v))}
                />
              </div>
            )}
            <div className="rounded-md bg-surface-2/30 px-2 py-1.5">
              <p className="text-xs italic text-muted">Key Contribution:</p>
              <EditableParagraph
                value={group.key_contribution}
                onCommit={(v) => persist(setGroupField(result, groupIdx, "key_contribution", v))}
                placeholder="No key contribution summary"
                className="text-xs italic text-muted"
              />
            </div>
          </div>
        ))}
      </Card>

      <Card className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-medium">Overall Impact</h2>
          <CopyButton
            text={bulletsToText(result.overall_impact.map((a) => `${a.category}: ${a.summary}`))}
          />
        </div>
        {result.overall_impact.length === 0 ? (
          <p className="text-sm text-muted">Nothing drafted for this section.</p>
        ) : (
          <ul className="space-y-1">
            {result.overall_impact.map((area, i) => (
              <li key={i} className="flex items-start gap-2">
                <EditableLine
                  value={area.category}
                  onCommit={(v) => persist(setImpactField(result, i, "category", v))}
                  className="w-40 shrink-0 font-medium"
                />
                <EditableParagraph
                  value={area.summary}
                  onCommit={(v) => persist(setImpactField(result, i, "summary", v))}
                  className="flex-1"
                />
                <RemoveIconButton
                  label={`the "${area.category || "untitled"}" impact area`}
                  onConfirm={() => persist(removeImpactArea(result, i))}
                />
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-medium">Team Support &amp; Collaboration</h2>
          <CopyButton text={sectionText("Team Support & Collaboration", result.team_support_bullets)} />
        </div>
        <EditableBulletList
          bullets={result.team_support_bullets}
          itemLabel="this bullet"
          onEdit={(i, v) => persist(setFlatBullet(result, "team_support_bullets", i, v))}
          onRemove={(i) => persist(removeFlatBullet(result, "team_support_bullets", i))}
        />
      </Card>

      <Card className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-medium">Learning &amp; Development</h2>
          <CopyButton text={sectionText("Learning & Development", result.learning_bullets)} />
        </div>
        <EditableBulletList
          bullets={result.learning_bullets}
          itemLabel="this bullet"
          onEdit={(i, v) => persist(setFlatBullet(result, "learning_bullets", i, v))}
          onRemove={(i) => persist(removeFlatBullet(result, "learning_bullets", i))}
        />
      </Card>

      <div className="flex justify-end gap-2">
        <a href={`/api/bff/brag-document-jobs/${job.id}/export?format=pdf`} target="_blank" rel="noreferrer">
          <Button variant="secondary">
            <FileText size={14} /> Download PDF
          </Button>
        </a>
        <a href={`/api/bff/brag-document-jobs/${job.id}/export?format=docx`} target="_blank" rel="noreferrer">
          <Button variant="secondary">
            <Download size={14} /> Download DOCX
          </Button>
        </a>
      </div>
    </div>
  );
}
