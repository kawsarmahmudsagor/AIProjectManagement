import { apiFetch } from "@/lib/api-client";
import type { ExtractionJobStatus, UploadResponse } from "@/lib/types";

// Kept in sync with backend/app/core/config.py's max_upload_size_mb — checked
// client-side only so a huge file fails fast instead of after a slow upload; the
// server enforces its own limit regardless.
export const MAX_UPLOAD_SIZE_MB = 25;

// backend/app/ingest/extract.py's magic-byte sniff accepts any UTF-8 text regardless of
// extension (that's the .txt fallback path) — .md rides the same path, no backend
// change needed, this list is purely the client-side UX gate.
export const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md"];

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<UploadResponse>("documents", { method: "POST", body: form });
}

export async function getExtractionJob(jobId: string): Promise<ExtractionJobStatus> {
  return apiFetch<ExtractionJobStatus>(`extraction-jobs/${jobId}`);
}

export async function cancelExtractionJob(jobId: string): Promise<ExtractionJobStatus> {
  return apiFetch<ExtractionJobStatus>(`extraction-jobs/${jobId}/cancel`, { method: "POST" });
}
