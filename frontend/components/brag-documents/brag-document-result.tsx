"use client";

import { Copy, Download, FileText } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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

export function BragDocumentResult({ job }: { job: BragDocumentJob }) {
  const result = job.result;
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
          <p className="text-sm text-muted">Review each section below — copy what you need into the ERP.</p>
        </div>
        <CopyButton text={fullText} label="Copy All" />
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
        {result.technical_contributions.map((group) => (
          <div key={group.project_name} className="space-y-2 rounded-lg border border-border p-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium">{group.project_name}</p>
              <CopyButton text={groupText(group)} />
            </div>
            {group.subsections.map((sub, i) => (
              <div key={i} className="space-y-1">
                <p className="text-xs font-medium text-muted">{sub.heading}</p>
                <ul className="list-disc space-y-1 pl-5 text-sm">
                  {sub.bullets.map((bullet, j) => (
                    <li key={j}>{bullet}</li>
                  ))}
                </ul>
              </div>
            ))}
            {group.bullets.length > 0 && (
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {group.bullets.map((bullet, i) => (
                  <li key={i}>{bullet}</li>
                ))}
              </ul>
            )}
            {group.key_contribution && (
              <p className="rounded-md bg-surface-2/30 px-2 py-1.5 text-xs italic text-muted">
                Key Contribution: {group.key_contribution}
              </p>
            )}
          </div>
        ))}
      </Card>

      {result.overall_impact.length > 0 && (
        <Card className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-medium">Overall Impact</h2>
            <CopyButton
              text={bulletsToText(result.overall_impact.map((a) => `${a.category}: ${a.summary}`))}
            />
          </div>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {result.overall_impact.map((area, i) => (
              <li key={i}>
                <span className="font-medium">{area.category}:</span> {area.summary}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-medium">Team Support &amp; Collaboration</h2>
          <CopyButton text={sectionText("Team Support & Collaboration", result.team_support_bullets)} />
        </div>
        {result.team_support_bullets.length === 0 ? (
          <p className="text-sm text-muted">Nothing drafted for this section.</p>
        ) : (
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {result.team_support_bullets.map((bullet, i) => (
              <li key={i}>{bullet}</li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-medium">Learning &amp; Development</h2>
          <CopyButton text={sectionText("Learning & Development", result.learning_bullets)} />
        </div>
        {result.learning_bullets.length === 0 ? (
          <p className="text-sm text-muted">Nothing drafted for this section.</p>
        ) : (
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {result.learning_bullets.map((bullet, i) => (
              <li key={i}>{bullet}</li>
            ))}
          </ul>
        )}
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
