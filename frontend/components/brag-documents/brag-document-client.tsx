"use client";

import { AlertCircle, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { JobStageStepper } from "@/components/ui/job-stage-stepper";
import {
  BRAG_DOCUMENT_STAGE_ORDER,
  bragDocumentStageLabel,
} from "@/components/brag-documents/brag-document-constants";
import { BragDocumentHistory } from "@/components/brag-documents/brag-document-history";
import { BragDocumentLauncher } from "@/components/brag-documents/brag-document-launcher";
import { BragDocumentResult } from "@/components/brag-documents/brag-document-result";
import { useBragDocumentJob, useCancelBragDocumentJob } from "@/hooks/use-brag-document-job";

const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);

export function BragDocumentClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const jobId = searchParams.get("job");
  const isNew = searchParams.get("new") === "1";
  const [cancelling, setCancelling] = useState(false);

  const job = useBragDocumentJob(jobId);
  const cancelJob = useCancelBragDocumentJob(jobId ?? "");

  function setJobId(id: string) {
    router.replace(`/brag-documents?job=${id}`);
  }

  function startOver() {
    router.replace("/brag-documents?new=1");
  }

  if (!jobId) {
    return isNew ? <BragDocumentLauncher onJobCreated={setJobId} /> : <BragDocumentHistory />;
  }

  if (job.isLoading || !job.data) {
    return <p className="text-sm text-muted">Loading…</p>;
  }

  const status = job.data.status;
  const currentStageIndex = (BRAG_DOCUMENT_STAGE_ORDER as readonly string[]).indexOf(status);
  const isPolling = !TERMINAL.has(status);

  if (isPolling) {
    return (
      <Card className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm font-medium">{bragDocumentStageLabel(status)}</p>
          <Button
            type="button"
            variant="ghost"
            disabled={cancelling}
            onClick={async () => {
              setCancelling(true);
              try {
                await cancelJob.mutateAsync();
              } finally {
                setCancelling(false);
              }
            }}
          >
            {cancelling ? "Cancelling…" : "Cancel"}
          </Button>
        </div>
        <JobStageStepper stages={BRAG_DOCUMENT_STAGE_ORDER} currentIndex={currentStageIndex} active />
      </Card>
    );
  }

  if (status === "cancelled") {
    return (
      <Card className="space-y-3">
        <div className="flex items-start gap-3">
          <X className="mt-0.5 shrink-0 text-muted" size={20} />
          <p className="text-sm text-muted">Cancelled before it finished.</p>
        </div>
        <div className="flex justify-end">
          <Button type="button" variant="secondary" onClick={startOver}>
            Try again
          </Button>
        </div>
      </Card>
    );
  }

  if (status === "failed") {
    return (
      <Card className="space-y-3 border-danger/40">
        <div className="flex items-start gap-3">
          <AlertCircle className="mt-0.5 shrink-0 text-danger" size={20} />
          <div className="space-y-1">
            <p className="text-sm font-medium text-danger">Couldn&apos;t generate the brag document</p>
            <p className="text-sm text-muted">{job.data.error_message}</p>
          </div>
        </div>
        <div className="flex justify-end">
          <Button type="button" variant="secondary" onClick={startOver}>
            Upload a different file
          </Button>
        </div>
      </Card>
    );
  }

  // status === "succeeded"
  return <BragDocumentResult job={job.data} />;
}
