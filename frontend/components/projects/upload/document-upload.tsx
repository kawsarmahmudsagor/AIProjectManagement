"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { AlertCircle, CheckCircle2, Loader2, UploadCloud, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useExtractionJob } from "@/hooks/use-extraction-job";
import { useShowProviderErrorModal } from "@/components/layout/provider-error-modal";
import { ApiError } from "@/lib/api-client";
import { ACCEPTED_EXTENSIONS, MAX_UPLOAD_SIZE_MB, cancelExtractionJob, uploadDocument } from "@/lib/documents";
import { cn } from "@/lib/utils";
import type { ExtractedProject, ExtractionResult, JobStatus } from "@/lib/types";

type Phase = "idle" | "uploading" | "polling" | "done" | "error" | "cancelled";

const STAGE_ORDER = ["queued", "parsing", "extracting", "structuring"] as const;
type Stage = (typeof STAGE_ORDER)[number];
const STAGE_LABELS: Record<Stage, string> = {
  queued: "Queued",
  parsing: "Reading document",
  extracting: "Finding project details",
  structuring: "Structuring results",
};

function stageLabel(status: JobStatus | undefined): string {
  if (status && (STAGE_ORDER as readonly string[]).includes(status)) return STAGE_LABELS[status as Stage];
  return "Working…";
}

function validateFile(file: File): string | null {
  const ext = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
  if (!ACCEPTED_EXTENSIONS.includes(ext)) {
    return `${file.name} isn't a PDF, DOCX, text, or Markdown file — try one of those formats instead.`;
  }
  if (file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024) {
    return `${file.name} is larger than the ${MAX_UPLOAD_SIZE_MB}MB limit.`;
  }
  return null;
}

// Which top-level fields the AI left empty — mirrors the no-hallucination failsafe: a
// field the document didn't state comes back null/empty rather than guessed, so the
// human sees exactly what still needs a manual pass.
function emptyFieldLabels(project: ExtractedProject): string[] {
  const labels: string[] = [];
  if (!project.name) labels.push("Project name");
  if (!project.role) labels.push("Your role");
  if (!project.start_date) labels.push("Start date");
  if (!project.end_date) labels.push("End date");
  if (!project.description.long.text.trim()) labels.push("Description (long form)");
  if (!project.description.short.text.trim()) labels.push("Description (short summary)");
  if (!project.responsibilities.long.text.trim()) labels.push("Responsibilities (long form)");
  if (!project.responsibilities.short.text.trim()) labels.push("Responsibilities (short summary)");
  if (project.technologies.length === 0) labels.push("Technologies");
  return labels;
}

export function DocumentUpload({
  onExtracted,
  disabled,
}: {
  /** Called once, the moment a job succeeds — the parent decides how to merge the
   * result into the form (never this component's job: it only ever hands over a
   * suggestion, matching the accept-don't-overwrite rule used for per-field AI
   * enhance elsewhere in this form). */
  onExtracted: (result: ExtractionResult) => void;
  disabled?: boolean;
}) {
  // `phase` only tracks what THIS component's own actions decided (idle -> uploading ->
  // polling, or back to idle on reset) — it deliberately never gets set to "done"/"error"
  // by the query result. Those two are derived from `job.data` below instead, so the
  // transition renders straight to the right frame with no intermediate "sync" Effect
  // (see the comment on DualEditorField's autofill handling for why that matters here).
  const [phase, setPhase] = useState<Phase>("idle");
  const [fileName, setFileName] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<{ code?: string; message: string } | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const appliedRef = useRef(false);
  const onExtractedRef = useRef(onExtracted);
  useEffect(() => {
    onExtractedRef.current = onExtracted;
  });

  const job = useExtractionJob(phase === "polling" ? jobId : null);
  const showProviderError = useShowProviderErrorModal();
  const shownErrorForJobRef = useRef<string | null>(null);

  // The only genuine side effect here — telling the parent a result arrived — belongs in
  // an Effect (it's a call into an external system, not a state update); it does not
  // itself set any React state, so it isn't a "setState in an Effect" sync-from-props
  // case, just a plain one-shot notification.
  useEffect(() => {
    if (job.data?.status === "succeeded" && job.data.result && !appliedRef.current) {
      appliedRef.current = true;
      onExtractedRef.current(job.data.result);
    }
  }, [job.data]);

  // Same shape: a one-shot notification to an external system (the global modal), keyed
  // per job so a later poll tick or a fresh upload doesn't re-open a dismissed popup.
  useEffect(() => {
    if (job.data?.status === "failed" && job.data.error && shownErrorForJobRef.current !== jobId) {
      if (showProviderError(job.data.error)) shownErrorForJobRef.current = jobId;
    }
  }, [job.data, jobId, showProviderError]);

  const effectivePhase: Phase =
    phase === "polling"
      ? job.data?.status === "succeeded"
        ? "done"
        : job.data?.status === "failed"
          ? "error"
          : job.data?.status === "cancelled"
            ? "cancelled"
            : "polling"
      : phase;

  const displayError =
    phase === "polling" && job.data?.status === "failed" ? (job.data.error ?? { message: "Extraction failed" }) : uploadError;

  const missingFields =
    effectivePhase === "done" && job.data?.result ? emptyFieldLabels(job.data.result.project) : [];

  const handleFile = async (file: File) => {
    const validationError = validateFile(file);
    if (validationError) {
      setFileName(file.name);
      setUploadError({ message: validationError });
      setPhase("error");
      return;
    }

    appliedRef.current = false;
    setFileName(file.name);
    setUploadError(null);
    setPhase("uploading");

    try {
      const { job_id } = await uploadDocument(file);
      setJobId(job_id);
      setPhase("polling");
    } catch (err) {
      setUploadError({
        code: err instanceof ApiError ? err.code : undefined,
        message: err instanceof ApiError ? err.message : "Upload failed — try again",
      });
      setPhase("error");
    }
  };

  const reset = () => {
    setPhase("idle");
    setFileName(null);
    setJobId(null);
    setUploadError(null);
    setCancelling(false);
    appliedRef.current = false;
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleCancel = async () => {
    if (!jobId || cancelling) return;
    setCancelling(true);
    try {
      await cancelExtractionJob(jobId);
      setPhase("cancelled");
    } catch {
      // Best effort — the worker may still stop on its own via the abort poll even if
      // this request failed; let the user retry the cancel rather than losing the job.
      setCancelling(false);
    }
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(false);
    if (disabled) return;
    const file = e.dataTransfer.files?.[0];
    if (file) void handleFile(file);
  };

  const busy = effectivePhase === "uploading" || effectivePhase === "polling";
  const currentStageIndex = job.data?.status ? (STAGE_ORDER as readonly string[]).indexOf(job.data.status) : -1;

  if (effectivePhase === "idle") {
    return (
      <Card
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (!disabled && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={onDrop}
        className={cn(
          "flex cursor-pointer flex-col items-center gap-2 border-2 border-dashed border-border bg-surface-2/30 py-10 text-center transition-colors",
          dragActive && "border-accent bg-accent/5",
          disabled && "cursor-not-allowed opacity-60",
        )}
      >
        <UploadCloud className="text-muted" size={28} />
        <p className="text-sm font-medium">Drop a project document, or click to browse</p>
        <p className="text-xs text-muted">PDF, DOCX, TXT, or Markdown — up to {MAX_UPLOAD_SIZE_MB}MB</p>
        <p className="text-xs text-muted">
          The AI fills in what it finds below; anything it can&apos;t find is left empty for you to add.
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(",")}
          disabled={disabled}
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleFile(file);
          }}
        />
      </Card>
    );
  }

  if (busy) {
    return (
      <Card className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Loader2 className="animate-spin text-accent" size={20} />
            <div>
              <p className="text-sm font-medium">
                {effectivePhase === "uploading" ? "Uploading…" : stageLabel(job.data?.status)}
              </p>
              <p className="text-xs text-muted">{fileName}</p>
            </div>
          </div>
          {effectivePhase === "polling" && (
            <Button type="button" variant="ghost" onClick={handleCancel} disabled={cancelling}>
              {cancelling ? "Cancelling…" : "Cancel"}
            </Button>
          )}
        </div>
        <div className="flex gap-1.5">
          {STAGE_ORDER.map((stage, i) => (
            <div
              key={stage}
              className={cn(
                "h-1 flex-1 rounded-full bg-surface-2",
                i <= currentStageIndex && effectivePhase === "polling" && "bg-accent",
              )}
            />
          ))}
        </div>
      </Card>
    );
  }

  if (effectivePhase === "cancelled") {
    return (
      <Card className="space-y-3">
        <div className="flex items-start gap-3">
          <X className="mt-0.5 shrink-0 text-muted" size={20} />
          <div className="space-y-1">
            <p className="text-sm font-medium">Cancelled {fileName ?? "that file"}</p>
            <p className="text-sm text-muted">Extraction was stopped before it finished.</p>
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={reset}>
            Try again
          </Button>
        </div>
      </Card>
    );
  }

  if (effectivePhase === "error") {
    return (
      <Card className="space-y-3 border-danger/40">
        <div className="flex items-start gap-3">
          <AlertCircle className="mt-0.5 shrink-0 text-danger" size={20} />
          <div className="space-y-1">
            <p className="text-sm font-medium text-danger">Couldn&apos;t process {fileName ?? "that file"}</p>
            <p className="text-sm text-muted">{displayError?.message}</p>
            {displayError?.code === "PROVIDER_NOT_CONFIGURED" && (
              <Link href="/settings/ai-providers" className="text-sm text-accent hover:underline">
                Go to Settings to add an API key
              </Link>
            )}
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={reset}>
            Try again
          </Button>
        </div>
      </Card>
    );
  }

  // effectivePhase === "done"
  return (
    <Card className="space-y-3 border-success/40">
      <div className="flex items-start gap-3">
        <CheckCircle2 className="mt-0.5 shrink-0 text-success" size={20} />
        <div className="space-y-1">
          <p className="text-sm font-medium">Filled in what we found in {fileName}</p>
          <p className="text-sm text-muted">Review the form below — nothing was guessed, so check it over before saving.</p>
          {missingFields.length > 0 && (
            <p className="text-sm text-muted">
              Not found, left for you to fill in: <span className="text-foreground">{missingFields.join(", ")}</span>
            </p>
          )}
        </div>
      </div>
      <div className="flex justify-end">
        <Button type="button" variant="ghost" onClick={reset}>
          <X size={14} /> Upload a different file
        </Button>
      </div>
    </Card>
  );
}
