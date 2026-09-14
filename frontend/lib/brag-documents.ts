import { apiFetch } from "@/lib/api-client";
import type {
  BragDocumentCreatePayload,
  BragDocumentJob,
  BragDocumentJobListResponse,
  BragDocumentPreviewResponse,
  BragDocumentResult,
} from "@/lib/types";

// The backend's preview endpoint reads .xlsx bytes directly via openpyxl (it bypasses the
// general ingest/extract.py pipeline, which would misclassify .xlsx as .docx via
// zip-magic) — so only Excel workbooks are accepted here, unlike documents.ts's broader
// PDF/DOCX/TXT/MD list.
export const BRAG_DOCUMENT_ACCEPTED_EXTENSIONS = [".xlsx"];

export async function previewStandupUpload(file: File): Promise<BragDocumentPreviewResponse> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<BragDocumentPreviewResponse>("brag-documents/preview", { method: "POST", body: form });
}

export async function createBragDocument(payload: BragDocumentCreatePayload): Promise<{ id: string }> {
  return apiFetch<{ id: string }>("brag-documents", { method: "POST", body: JSON.stringify(payload) });
}

export async function listBragDocumentJobs(): Promise<BragDocumentJobListResponse> {
  return apiFetch<BragDocumentJobListResponse>("brag-document-jobs?page=1&page_size=50");
}

export async function getBragDocumentJob(jobId: string): Promise<BragDocumentJob> {
  return apiFetch<BragDocumentJob>(`brag-document-jobs/${jobId}`);
}

export async function cancelBragDocumentJob(jobId: string): Promise<BragDocumentJob> {
  return apiFetch<BragDocumentJob>(`brag-document-jobs/${jobId}/cancel`, { method: "POST" });
}

export async function deleteBragDocumentJob(jobId: string): Promise<void> {
  return apiFetch<void>(`brag-document-jobs/${jobId}`, { method: "DELETE" });
}

// `result` is the whole edited document (text edits and/or removed bullets/groups) —
// autosaved on every change, so this always sends the complete current shape rather
// than a partial diff.
export async function updateBragDocumentResult(
  jobId: string,
  result: BragDocumentResult,
): Promise<BragDocumentJob> {
  return apiFetch<BragDocumentJob>(`brag-document-jobs/${jobId}`, {
    method: "PATCH",
    body: JSON.stringify(result),
  });
}

export async function resetBragDocumentEdits(jobId: string): Promise<BragDocumentJob> {
  return apiFetch<BragDocumentJob>(`brag-document-jobs/${jobId}/reset`, { method: "POST" });
}
