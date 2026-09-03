import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col items-center gap-3 py-16 text-center">
      <h1 className="text-xl font-semibold">Project not found</h1>
      <p className="text-sm text-muted">
        It may have been deleted, or you don&apos;t have access to it.
      </p>
      <Link href="/projects">
        <Button variant="secondary">Back to projects</Button>
      </Link>
    </div>
  );
}
