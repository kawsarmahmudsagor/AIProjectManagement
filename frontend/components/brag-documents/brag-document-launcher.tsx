"use client";

import { AlertCircle, FileSpreadsheet, Loader2, UploadCloud } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toaster";
import { ApiError } from "@/lib/api-client";
import { BRAG_DOCUMENT_ACCEPTED_EXTENSIONS, createBragDocument, previewStandupUpload } from "@/lib/brag-documents";
import { MAX_UPLOAD_SIZE_MB } from "@/lib/documents";
import type { BragDocumentPreviewResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

function validateFile(file: File): string | null {
  const ext = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
  if (!BRAG_DOCUMENT_ACCEPTED_EXTENSIONS.includes(ext)) {
    return `${file.name} isn't an Excel (.xlsx) file — export the standup workbook as .xlsx and try again.`;
  }
  if (file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024) {
    return `${file.name} is larger than the ${MAX_UPLOAD_SIZE_MB}MB limit.`;
  }
  return null;
}

/** Upload the monthly standup workbook, then confirm the auto-matched (or manually
 * picked) member name and target month before a BragDocumentJob is created. Kept as its
 * own component (not a reuse of components/projects/upload/document-upload.tsx) because
 * this flow has a member/month confirmation step with no equivalent there. */
export function BragDocumentLauncher({ onJobCreated }: { onJobCreated: (jobId: string) => void }) {
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [preview, setPreview] = useState<BragDocumentPreviewResponse | null>(null);
  const [memberName, setMemberName] = useState("");
  const [targetMonth, setTargetMonth] = useState("");
  const [generating, setGenerating] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  async function handleFile(file: File) {
    const validationError = validateFile(file);
    if (validationError) {
      setFileName(file.name);
      setUploadError(validationError);
      return;
    }
    setFileName(file.name);
    setUploadError(null);
    setUploading(true);
    try {
      const result = await previewStandupUpload(file);
      setPreview(result);
      setMemberName(result.detected_member_name ?? "");
      setTargetMonth(result.available_months[0] ?? "");
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "Couldn't read that spreadsheet — try again.");
    } finally {
      setUploading(false);
    }
  }

  function reset() {
    setPreview(null);
    setFileName(null);
    setUploadError(null);
    setMemberName("");
    setTargetMonth("");
    if (inputRef.current) inputRef.current.value = "";
  }

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(false);
    if (uploading) return;
    const file = e.dataTransfer.files?.[0];
    if (file) void handleFile(file);
  };

  async function handleGenerate() {
    if (!preview || !memberName || !targetMonth) return;
    setGenerating(true);
    try {
      const job = await createBragDocument({
        document_id: preview.document_id,
        member_name: memberName,
        target_month: targetMonth,
      });
      onJobCreated(job.id);
    } catch (err) {
      toast({
        variant: "error",
        message: err instanceof ApiError ? err.message : "Couldn't start the brag document. Try again.",
      });
      setGenerating(false);
    }
  }

  if (!preview) {
    return (
      <Card
        role="button"
        tabIndex={uploading ? -1 : 0}
        aria-disabled={uploading}
        onClick={() => !uploading && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (!uploading && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!uploading) setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={onDrop}
        className={cn(
          "flex cursor-pointer flex-col items-center gap-2 border-2 border-dashed border-border bg-surface-2/30 py-10 text-center transition-colors",
          dragActive && "border-accent bg-accent/5",
          uploading && "cursor-not-allowed opacity-60",
        )}
      >
        {uploading ? (
          <Loader2 className="animate-spin text-accent" size={28} />
        ) : (
          <UploadCloud className="text-muted" size={28} />
        )}
        <p className="text-sm font-medium">
          {uploading ? `Reading ${fileName}…` : "Drop the monthly standup workbook, or click to browse"}
        </p>
        <p className="text-xs text-muted">Excel (.xlsx) — up to {MAX_UPLOAD_SIZE_MB}MB</p>
        <input
          ref={inputRef}
          type="file"
          accept={BRAG_DOCUMENT_ACCEPTED_EXTENSIONS.join(",")}
          disabled={uploading}
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleFile(file);
          }}
        />
        {uploadError && (
          <p className="mt-2 flex items-center gap-1.5 text-sm text-danger">
            <AlertCircle size={14} /> {uploadError}
          </p>
        )}
      </Card>
    );
  }

  // Union with detected_member_name in case the backend's candidate list doesn't already
  // include it — the pre-fill must always be a selectable option.
  const memberOptions = Array.from(
    new Set([...(preview.detected_member_name ? [preview.detected_member_name] : []), ...preview.candidate_member_names]),
  );

  return (
    <Card className="space-y-4">
      <div className="flex items-start gap-3">
        <FileSpreadsheet className="mt-0.5 shrink-0 text-accent" size={20} />
        <div>
          <p className="text-sm font-medium">{fileName}</p>
          <p className="text-sm text-muted">
            {preview.detected_member_name
              ? `Matched "${preview.detected_member_name}" (${Math.round(preview.match_confidence * 100)}% confidence) — confirm or change below.`
              : "Couldn't confidently match a name in the sheet — pick yours below."}
          </p>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <label htmlFor="brag-member" className="block text-sm font-medium">
            Team member
          </label>
          {memberOptions.length > 0 ? (
            <Select
              id="brag-member"
              value={memberName}
              onChange={(e) => setMemberName(e.target.value)}
              className="w-full"
            >
              {!memberOptions.includes(memberName) && <option value="">Select…</option>}
              {memberOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Select>
          ) : (
            <input
              id="brag-member"
              type="text"
              value={memberName}
              onChange={(e) => setMemberName(e.target.value)}
              placeholder="Type the exact name as it appears in the sheet"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50"
            />
          )}
        </div>

        <div className="space-y-1">
          <label htmlFor="brag-month" className="block text-sm font-medium">
            Month
          </label>
          <Select id="brag-month" value={targetMonth} onChange={(e) => setTargetMonth(e.target.value)} className="w-full">
            <option value="" disabled>
              Select…
            </option>
            {preview.available_months.map((month) => (
              <option key={month} value={month}>
                {month}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <div className="flex justify-between">
        <Button type="button" variant="ghost" onClick={reset} disabled={generating}>
          Upload a different file
        </Button>
        <Button type="button" onClick={handleGenerate} disabled={!memberName || !targetMonth || generating}>
          {generating ? "Starting…" : "Generate"}
        </Button>
      </div>
    </Card>
  );
}
