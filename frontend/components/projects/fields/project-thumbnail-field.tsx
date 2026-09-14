"use client";

import { ImageIcon, Sparkles, Trash2, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { JobStageStepper } from "@/components/ui/job-stage-stepper";
import { useThumbnailJob } from "@/hooks/use-thumbnail-job";
import type { AiGlowState } from "@/lib/ai-glow";
import { ApiError } from "@/lib/api-client";
import { mediaUrl } from "@/lib/media-url";
import {
  deleteProjectThumbnail,
  startThumbnailGeneration,
  uploadProjectThumbnail,
  validateImage,
} from "@/lib/project-media";
import type { ThumbnailGenerationContext } from "@/lib/types";
import { cn } from "@/lib/utils";

const GENERATE_STAGE_ORDER = ["queued", "parsing", "extracting", "structuring"] as const;
const GENERATE_STAGE_LABELS: Record<(typeof GENERATE_STAGE_ORDER)[number], string> = {
  queued: "Queued",
  parsing: "Designing the thumbnail",
  extracting: "Generating the image",
  structuring: "Rendering a poster instead",
};

/** Top-left thumbnail section of the project form. `hasContext` is driven by the
 * parent's useWatch (so the Generate button reacts live as the user types, matching
 * DualEditorField's reactive empty-checks). In create mode (no `projectId` yet),
 * clicking Generate first calls `ensureSaved()` — per the product decision to auto-save
 * the project before generating rather than send unsaved-form context inline — and only
 * proceeds once that resolves to a real id. */
export function ProjectThumbnailField({
  projectId,
  thumbnailUrl,
  onThumbnailChange,
  hasContext,
  buildContext,
  ensureSaved,
  disabled,
}: {
  projectId: string | null;
  thumbnailUrl: string | null;
  onThumbnailChange: (url: string | null) => void;
  hasContext: boolean;
  buildContext: () => ThumbnailGenerationContext;
  /** In create mode, saves the project and returns its new id (or null if the save
   * itself failed validation — e.g. a required field is still empty). Already-saved
   * projects (edit mode) just return `projectId` immediately without a network call. */
  ensureSaved: () => Promise<string | null>;
  disabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  const job = useThumbnailJob(jobId);
  // Guards the notification below to one-shot, exactly matching
  // document-upload.tsx's appliedRef pattern — that effect calls ONLY a prop callback
  // and mutates this ref, never a local setState, which is what keeps it outside
  // react-hooks/set-state-in-effect's rule. Job-status transitions (busy -> done/error)
  // are derived directly from `job.data` at render time below, not stored, for the same
  // reason document-upload.tsx derives `effectivePhase` instead of syncing it into state.
  const appliedRef = useRef(false);

  useEffect(() => {
    if (!job.data || appliedRef.current) return;
    if (job.data.status === "succeeded" && job.data.result) {
      appliedRef.current = true;
      // The backend's media URL already embeds a content hash (?v=<sha256 prefix>,
      // see backend/app/services/project_media_service.media_ref) — a fresh
      // generation always produces a different URL string, so no client-side
      // cache-busting is needed the way photo-upload.tsx needs one for its stable
      // /api/v1/profile/photo URL.
      onThumbnailChange(job.data.result.url);
    } else if (job.data.status === "failed") {
      appliedRef.current = true;
    }
  }, [job.data, onThumbnailChange]);

  // Derived from job.data at render time rather than copied into local state via the
  // effect above — this is what keeps that effect free of any setState call (only a
  // prop callback + a ref mutation, matching document-upload.tsx's own one-shot
  // notification pattern exactly).
  const jobError = job.data?.status === "failed" ? (job.data.error?.message ?? "Thumbnail generation failed.") : null;
  const jobIsTerminal = job.data?.status === "succeeded" || job.data?.status === "failed" || job.data?.status === "cancelled";
  const generating = jobId !== null && !jobIsTerminal;
  const glow: AiGlowState = generating ? "generating" : "idle";
  const displayError = error ?? jobError;

  const onFileChange = async (file: File | undefined) => {
    if (!file) return;
    const validationError = validateImage(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const id = await ensureSaved();
      if (!id) return;
      const result = await uploadProjectThumbnail(id, file);
      onThumbnailChange(result.url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not upload thumbnail");
    } finally {
      setBusy(false);
    }
  };

  const onGenerate = async () => {
    if (!hasContext) {
      setError(
        "Add the project name and either a description or some technologies first — the thumbnail is generated from your project's own details.",
      );
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const id = await ensureSaved();
      if (!id) return;
      appliedRef.current = false;
      const { job_id } = await startThumbnailGeneration(id, buildContext());
      setJobId(job_id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start generation");
    } finally {
      setBusy(false);
    }
  };

  const onRemove = async () => {
    if (!projectId) {
      onThumbnailChange(null);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await deleteProjectThumbnail(projectId);
      onThumbnailChange(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not remove thumbnail");
    } finally {
      setBusy(false);
    }
  };

  const displayUrl = thumbnailUrl ? mediaUrl(thumbnailUrl) : null;
  const currentStageIndex = job.data?.status
    ? (GENERATE_STAGE_ORDER as readonly string[]).indexOf(job.data.status)
    : -1;

  return (
    <div className="w-full space-y-3 @2xl:w-[220px] @2xl:shrink-0">
      {/* .ai-glow's ring is drawn OUTSIDE the padding box (inset:-2px) — putting
          overflow-hidden on the SAME node would clip it, so the glow lives on this outer
          wrapper and overflow-hidden goes on the inner image box below it instead. */}
      <div className={cn("rounded-lg", glow !== "idle" && `ai-glow ai-glow--${glow}`)}>
        <div className="flex aspect-video w-full items-center justify-center overflow-hidden rounded-lg border border-border bg-surface-2">
          {displayUrl ? (
            // eslint-disable-next-line @next/next/no-img-element -- served from our own authenticated API
            <img src={displayUrl} alt="Project thumbnail" className="h-full w-full object-cover" />
          ) : generating ? (
            <div className="w-full space-y-2 px-4 text-center">
              <Sparkles size={20} className="mx-auto animate-pulse text-accent" />
              <p className="text-xs text-muted">
                {job.data?.status
                  ? GENERATE_STAGE_LABELS[job.data.status as (typeof GENERATE_STAGE_ORDER)[number]] ?? "Working…"
                  : "Starting…"}
              </p>
              <JobStageStepper stages={GENERATE_STAGE_ORDER} currentIndex={currentStageIndex} active />
            </div>
          ) : (
            <ImageIcon size={28} className="text-muted" />
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(e) => void onFileChange(e.target.files?.[0])}
        />
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={disabled || busy || generating}
          onClick={() => inputRef.current?.click()}
        >
          <Upload size={13} /> Upload
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={disabled || busy || generating}
          title={hasContext ? undefined : "Add a description or technologies first"}
          onClick={() => void onGenerate()}
        >
          <Sparkles size={13} /> Generate
        </Button>
        {displayUrl && (
          <Button type="button" variant="ghost" size="sm" disabled={disabled || busy} onClick={() => void onRemove()}>
            <Trash2 size={13} />
          </Button>
        )}
      </div>
      {displayError && <p className="text-xs text-danger">{displayError}</p>}
    </div>
  );
}
