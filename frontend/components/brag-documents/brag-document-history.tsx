"use client";

import { FileText, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useBragDocumentJobs } from "@/hooks/use-brag-document-job";
import { formatTimestamp } from "@/lib/dates";
import { cn } from "@/lib/utils";
import type { JobStatus } from "@/lib/types";

const STATUS_LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  parsing: "Reading spreadsheet",
  extracting: "Drafting",
  structuring: "Finalizing",
  succeeded: "Ready",
  failed: "Failed",
  cancelled: "Cancelled",
};

function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <Badge className={cn(status === "failed" && "bg-danger/10 text-danger")}>
      {STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

export function BragDocumentHistory() {
  const router = useRouter();
  const { data, isLoading, isError } = useBragDocumentJobs();

  function openNew() {
    router.push("/brag-documents?new=1");
  }

  function openJob(id: string) {
    router.push(`/brag-documents?job=${id}`);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Brag Documents</h1>
          <p className="text-sm text-muted">Monthly performance reports generated from your standup log.</p>
        </div>
        <Button type="button" onClick={openNew}>
          <Plus size={14} /> New Brag Document
        </Button>
      </div>

      {isLoading && <p className="text-sm text-muted">Loading…</p>}
      {isError && <p className="text-sm text-danger">Couldn&apos;t load your saved documents.</p>}

      {data && data.items.length === 0 && (
        <Card className="flex flex-col items-center gap-2 py-10 text-center">
          <FileText className="text-muted" size={28} />
          <p className="text-sm text-muted">You haven&apos;t generated a brag document yet.</p>
          <Button type="button" variant="secondary" onClick={openNew}>
            <Plus size={14} /> New Brag Document
          </Button>
        </Card>
      )}

      {data && data.items.length > 0 && (
        <Card className="divide-y divide-border p-0">
          {data.items.map((job) => (
            <div
              key={job.id}
              role="button"
              tabIndex={0}
              onClick={() => openJob(job.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  openJob(job.id);
                }
              }}
              className="flex cursor-pointer items-center justify-between gap-3 px-4 py-3 hover:bg-surface-2"
            >
              <div className="min-w-0">
                <p className="truncate font-medium">{job.name}</p>
                <p className="text-xs text-muted">
                  {job.member_name} &middot; {formatTimestamp(job.created_at)}
                </p>
              </div>
              <StatusBadge status={job.status} />
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
