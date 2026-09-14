"use client";

import { DocumentUpload } from "@/components/projects/upload/document-upload";
import { Dialog } from "@/components/ui/dialog";
import type { ExtractionResult } from "@/lib/types";

/** Replaces the old dropzone that used to sit at the top of the project form with a
 * dialog opened from the "Input" button at the top right — DocumentUpload's own 330
 * lines (phase machine, polling, the done/error/cancelled frames, the no-hallucination
 * missing-fields summary) are reused completely unchanged inside it. The merge contract
 * is untouched by construction: `onExtracted` still reads getValues()/dirtyFields in the
 * parent (project-form.tsx) at call time, so moving the trigger from an inline dropzone
 * to a dialog changes nothing about how a result gets merged into the form. */
export function ProjectInputDialog({
  open,
  onClose,
  onExtracted,
  disabled,
}: {
  open: boolean;
  onClose: () => void;
  onExtracted: (result: ExtractionResult) => void;
  disabled?: boolean;
}) {
  return (
    <Dialog open={open} onClose={onClose} title="Fill from a document" className="max-w-lg">
      <DocumentUpload onExtracted={onExtracted} disabled={disabled} />
    </Dialog>
  );
}
