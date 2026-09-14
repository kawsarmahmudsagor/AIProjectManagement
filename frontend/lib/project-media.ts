import { apiFetch } from "@/lib/api-client";
import type { ProjectMediaRef, ThumbnailGenerationContext, ThumbnailJobStatus } from "@/lib/types";

// Kept in sync with backend/app/core/config.py's max_thumbnail_size_mb/max_video_size_mb —
// checked client-side only so an oversized file fails fast; the server enforces its own
// limit regardless (routers/project_media.py's _read_capped).
export const MAX_THUMBNAIL_SIZE_MB = 5;
export const MAX_VIDEO_SIZE_MB = 50;

export const IMAGE_ACCEPT = "image/jpeg,image/png,image/webp";
export const VIDEO_ACCEPT = "video/mp4,video/webm";

export function validateImage(file: File): string | null {
  if (!file.type.startsWith("image/")) return `${file.name} isn't an image file.`;
  if (file.size > MAX_THUMBNAIL_SIZE_MB * 1024 * 1024) {
    return `${file.name} is larger than the ${MAX_THUMBNAIL_SIZE_MB}MB limit.`;
  }
  return null;
}

export function validateVideo(file: File): string | null {
  if (!file.type.startsWith("video/")) return `${file.name} isn't a video file.`;
  if (file.size > MAX_VIDEO_SIZE_MB * 1024 * 1024) {
    return `${file.name} is larger than the ${MAX_VIDEO_SIZE_MB}MB limit.`;
  }
  return null;
}

export async function uploadProjectThumbnail(projectId: string, file: File): Promise<ProjectMediaRef> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<ProjectMediaRef>(`projects/${projectId}/thumbnail`, { method: "PUT", body: form });
}

export async function deleteProjectThumbnail(projectId: string): Promise<void> {
  await apiFetch<void>(`projects/${projectId}/thumbnail`, { method: "DELETE" });
}

export async function uploadProjectVideo(projectId: string, file: File): Promise<ProjectMediaRef> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<ProjectMediaRef>(`projects/${projectId}/video`, { method: "PUT", body: form });
}

export async function deleteProjectVideo(projectId: string): Promise<void> {
  await apiFetch<void>(`projects/${projectId}/video`, { method: "DELETE" });
}

export async function startThumbnailGeneration(
  projectId: string,
  context: ThumbnailGenerationContext,
): Promise<{ job_id: string }> {
  return apiFetch<{ job_id: string }>(`projects/${projectId}/thumbnail/generate`, {
    method: "POST",
    body: JSON.stringify({ context }),
  });
}

export async function getThumbnailJob(jobId: string): Promise<ThumbnailJobStatus> {
  return apiFetch<ThumbnailJobStatus>(`thumbnail-jobs/${jobId}`);
}

export async function cancelThumbnailJob(jobId: string): Promise<ThumbnailJobStatus> {
  return apiFetch<ThumbnailJobStatus>(`thumbnail-jobs/${jobId}/cancel`, { method: "POST" });
}
