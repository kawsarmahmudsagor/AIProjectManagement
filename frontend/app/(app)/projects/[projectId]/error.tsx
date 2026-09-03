"use client";

import { Button } from "@/components/ui/button";

// Next.js 16: the recovery callback is `retry` (stable since v16.3.0), not the older
// `reset` — see node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/error.md.
export default function ErrorBoundary({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col items-center gap-3 py-16 text-center">
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p className="max-w-sm text-sm text-muted">{error.message || "An unexpected error occurred."}</p>
      <Button variant="secondary" onClick={() => retry()}>
        Try again
      </Button>
    </div>
  );
}
