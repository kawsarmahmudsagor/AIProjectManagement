import { Suspense } from "react";
import { BragDocumentClient } from "@/components/brag-documents/brag-document-client";

export default function BragDocumentsPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-1 text-2xl font-semibold">Brag Document Generator</h1>
      <p className="mb-6 text-sm text-muted">
        Upload the team&apos;s monthly standup workbook — the AI drafts your accomplishments grounded in your saved
        project context, alongside deterministic hour stats parsed straight from the sheet.
      </p>
      {/* useSearchParams (for ?job=) requires a Suspense boundary around its nearest client usage. */}
      <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}>
        <BragDocumentClient />
      </Suspense>
    </div>
  );
}
