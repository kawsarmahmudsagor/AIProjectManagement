"use client";

import { AlertCircle, X } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { JobStageStepper } from "@/components/ui/job-stage-stepper";
import { BREAKDOWN_STAGE_ORDER, breakdownStageLabel } from "@/components/breakdown/breakdown-constants";
import { BreakdownLauncher } from "@/components/breakdown/breakdown-launcher";
import { BreakdownReview } from "@/components/breakdown/breakdown-review";
import { useBreakdownJob, useCancelBreakdownJob } from "@/hooks/use-breakdown";

const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);

export function BreakdownClient({ projectId }: { projectId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const jobId = searchParams.get("job");
  const [cancelling, setCancelling] = useState(false);

  const job = useBreakdownJob(jobId);
  const cancelJob = useCancelBreakdownJob(jobId ?? "");

  function setJobId(id: string) {
    router.replace(`/projects/${projectId}/tasks/breakdown?job=${id}`);
  }

  if (!jobId) {
    return <BreakdownLauncher projectId={projectId} onJobCreated={setJobId} />;
  }

  if (job.isLoading || !job.data) {
    return <p className="text-sm text-muted">Loading…</p>;
  }

  const status = job.data.status;
  const currentStageIndex = (BREAKDOWN_STAGE_ORDER as readonly string[]).indexOf(status);
  const isPolling = !TERMINAL.has(status);

  if (isPolling) {
    return (
      <Card className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm font-medium">{breakdownStageLabel(status)}</p>
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
        <JobStageStepper stages={BREAKDOWN_STAGE_ORDER} currentIndex={currentStageIndex} active />
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
          <Button type="button" variant="secondary" onClick={() => router.replace(`/projects/${projectId}/tasks/breakdown`)}>
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
            <p className="text-sm font-medium text-danger">Couldn&apos;t generate a breakdown</p>
            <p className="text-sm text-muted">{job.data.error_message}</p>
            {job.data.error_code === "PROVIDER_NOT_CONFIGURED" && (
              <Link href="/settings/ai-providers" className="text-sm text-accent hover:underline">
                Go to Settings to add an API key
              </Link>
            )}
            {job.data.error_code === "TRUNCATED_RESPONSE" && (
              <p className="text-xs text-muted">Try again with a smaller task cap.</p>
            )}
          </div>
        </div>
        <div className="flex justify-end">
          <Button type="button" variant="secondary" onClick={() => router.replace(`/projects/${projectId}/tasks/breakdown`)}>
            Try again
          </Button>
        </div>
      </Card>
    );
  }

  // status === "succeeded"
  return <BreakdownReview projectId={projectId} job={job.data} />;
}
