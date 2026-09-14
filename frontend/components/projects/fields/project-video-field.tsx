"use client";

import { Trash2, Upload, Video } from "lucide-react";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api-client";
import { mediaUrl } from "@/lib/media-url";
import { deleteProjectVideo, uploadProjectVideo, validateVideo } from "@/lib/project-media";

/** Optional, user-uploaded only (no AI generation for video, unlike the thumbnail).
 * Plays on hover on the project card (components/projects/project-card-media.tsx) once
 * saved. Requires a saved project — `ensureSaved` mirrors ProjectThumbnailField's own
 * auto-save-first contract in create mode. */
export function ProjectVideoField({
  projectId,
  videoUrl,
  onVideoChange,
  ensureSaved,
  disabled,
}: {
  projectId: string | null;
  videoUrl: string | null;
  onVideoChange: (url: string | null) => void;
  ensureSaved: () => Promise<string | null>;
  disabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onFileChange = async (file: File | undefined) => {
    if (!file) return;
    const validationError = validateVideo(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const id = await ensureSaved();
      if (!id) return;
      const result = await uploadProjectVideo(id, file);
      onVideoChange(result.url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not upload video");
    } finally {
      setBusy(false);
    }
  };

  const onRemove = async () => {
    if (!projectId) {
      onVideoChange(null);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await deleteProjectVideo(projectId);
      onVideoChange(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not remove video");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <label className="mb-1 block text-sm font-medium">Project Video (Optional)</label>
      <p className="mb-2 text-xs text-muted">Plays automatically when someone hovers this project&apos;s card.</p>
      {videoUrl ? (
        <video src={mediaUrl(videoUrl)} controls muted preload="metadata" className="w-full max-w-sm rounded-lg border border-border" />
      ) : (
        <div className="flex aspect-video w-full max-w-sm items-center justify-center rounded-lg border border-dashed border-border bg-surface-2 text-muted">
          <Video size={24} />
        </div>
      )}
      <div className="mt-2 flex gap-2">
        <input ref={inputRef} type="file" accept="video/mp4,video/webm" className="hidden" onChange={(e) => void onFileChange(e.target.files?.[0])} />
        <Button type="button" variant="secondary" size="sm" disabled={disabled || busy} onClick={() => inputRef.current?.click()}>
          <Upload size={13} /> {videoUrl ? "Replace" : "Upload"} Video
        </Button>
        {videoUrl && (
          <Button type="button" variant="ghost" size="sm" disabled={disabled || busy} onClick={() => void onRemove()}>
            <Trash2 size={13} /> Remove
          </Button>
        )}
      </div>
      {error && <p className="mt-1 text-xs text-danger">{error}</p>}
    </div>
  );
}
