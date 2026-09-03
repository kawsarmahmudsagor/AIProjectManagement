"use client";

import { FileText, MessageSquareText, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/toaster";
import { useCreateBreakdown } from "@/hooks/use-breakdown";
import { ApiError } from "@/lib/api-client";
import { ACCEPTED_EXTENSIONS, MAX_UPLOAD_SIZE_MB } from "@/lib/documents";
import { uploadDocumentForBreakdown } from "@/lib/breakdown";

type Mode = "choose" | "upload" | "prompt";

export function BreakdownLauncher({
  projectId,
  onJobCreated,
}: {
  projectId: string;
  onJobCreated: (jobId: string) => void;
}) {
  const [mode, setMode] = useState<Mode>("choose");
  const [uploading, setUploading] = useState(false);
  const [prompt, setPrompt] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();
  const createBreakdown = useCreateBreakdown(projectId);

  async function handleFile(file: File) {
    const ext = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      toast({ variant: "error", message: `${file.name} isn't a PDF, DOCX, text, or Markdown file.` });
      return;
    }
    if (file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024) {
      toast({ variant: "error", message: `${file.name} is larger than the ${MAX_UPLOAD_SIZE_MB}MB limit.` });
      return;
    }
    setUploading(true);
    try {
      const { document_id } = await uploadDocumentForBreakdown(file);
      const job = await createBreakdown.mutateAsync({ document_id });
      onJobCreated(job.id);
    } catch (err) {
      toast({
        variant: "error",
        message: err instanceof ApiError ? err.message : "Upload failed — try again.",
      });
      setUploading(false);
    }
  }

  async function handlePromptSubmit() {
    if (!prompt.trim()) return;
    try {
      const job = await createBreakdown.mutateAsync({ prompt: prompt.trim() });
      onJobCreated(job.id);
    } catch {
      // useCreateBreakdown's onError already toasts.
    }
  }

  if (mode === "choose") {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        <Card
          role="button"
          tabIndex={0}
          onClick={() => setMode("upload")}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setMode("upload")}
          className="cursor-pointer space-y-2 text-center hover:border-accent/50"
        >
          <UploadCloud className="mx-auto text-muted" size={24} />
          <p className="text-sm font-medium">Upload a document</p>
          <p className="text-xs text-muted">A spec, SOW, or brief — PDF, DOCX, TXT, or Markdown.</p>
        </Card>
        <Card
          role="button"
          tabIndex={0}
          onClick={() => setMode("prompt")}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setMode("prompt")}
          className="cursor-pointer space-y-2 text-center hover:border-accent/50"
        >
          <MessageSquareText className="mx-auto text-muted" size={24} />
          <p className="text-sm font-medium">Describe the work</p>
          <p className="text-xs text-muted">No document handy? Just tell the AI what you need done.</p>
        </Card>
      </div>
    );
  }

  if (mode === "upload") {
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
        className="flex cursor-pointer flex-col items-center gap-2 border-2 border-dashed border-border py-10 text-center"
      >
        <FileText className="text-muted" size={24} />
        <p className="text-sm font-medium">
          {uploading ? "Uploading…" : "Click to choose a file"}
        </p>
        <p className="text-xs text-muted">PDF, DOCX, TXT, or Markdown — up to {MAX_UPLOAD_SIZE_MB}MB</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(",")}
          disabled={uploading}
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleFile(file);
          }}
        />
        <Button type="button" variant="ghost" onClick={(e) => { e.stopPropagation(); setMode("choose"); }} disabled={uploading}>
          Back
        </Button>
      </Card>
    );
  }

  return (
    <Card className="space-y-3">
      <label className="block text-sm font-medium" htmlFor="breakdown-prompt">
        Describe the work
      </label>
      <textarea
        id="breakdown-prompt"
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        rows={5}
        placeholder="e.g. Build a customer-facing billing dashboard with invoice history, payment method management, and usage-based alerts."
        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50"
      />
      <div className="flex justify-between">
        <Button type="button" variant="ghost" onClick={() => setMode("choose")}>
          Back
        </Button>
        <Button
          type="button"
          onClick={handlePromptSubmit}
          disabled={!prompt.trim() || createBreakdown.isPending}
        >
          {createBreakdown.isPending ? "Starting…" : "Break it down"}
        </Button>
      </div>
    </Card>
  );
}
