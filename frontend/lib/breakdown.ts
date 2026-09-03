import { apiFetch } from "@/lib/api-client";
import type {
  BreakdownAcceptItem,
  BreakdownAcceptResponse,
  BreakdownCreatePayload,
  BreakdownJob,
  UploadResponse,
} from "@/lib/types";

export async function uploadDocumentForBreakdown(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  // store_only: this flow creates its own BreakdownJob right after — no point also
  // paying for (and discarding) a full field-extraction job on the same upload.
  form.append("purpose", "store_only");
  return apiFetch<UploadResponse>("documents", { method: "POST", body: form });
}

export async function createBreakdown(
  projectId: string,
  payload: BreakdownCreatePayload,
): Promise<{ id: string }> {
  return apiFetch<{ id: string }>(`projects/${projectId}/breakdowns`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getBreakdownJob(jobId: string): Promise<BreakdownJob> {
  return apiFetch<BreakdownJob>(`breakdown-jobs/${jobId}`);
}

export async function cancelBreakdownJob(jobId: string): Promise<BreakdownJob> {
  return apiFetch<BreakdownJob>(`breakdown-jobs/${jobId}/cancel`, { method: "POST" });
}

export async function acceptBreakdownItems(
  jobId: string,
  items: BreakdownAcceptItem[],
  dryRun = false,
): Promise<BreakdownAcceptResponse> {
  return apiFetch<BreakdownAcceptResponse>(`breakdown-jobs/${jobId}/accept`, {
    method: "POST",
    body: JSON.stringify({ items, dry_run: dryRun }),
  });
}

export async function dismissBreakdownRefs(jobId: string, refs: string[]): Promise<BreakdownJob> {
  return apiFetch<BreakdownJob>(`breakdown-jobs/${jobId}/dismiss`, {
    method: "POST",
    body: JSON.stringify({ refs }),
  });
}
