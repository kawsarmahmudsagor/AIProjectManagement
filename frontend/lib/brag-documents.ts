import { apiFetch } from "@/lib/api-client";
import type {
  BragDocumentCreatePayload,
  BragDocumentJob,
  BragDocumentJobListResponse,
  BragDocumentPreviewResponse,
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
