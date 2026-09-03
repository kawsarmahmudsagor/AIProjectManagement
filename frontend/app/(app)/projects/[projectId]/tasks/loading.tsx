import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="mx-auto max-w-3xl">
      <Skeleton className="mb-2 h-4 w-32" />
      <Skeleton className="mb-6 h-8 w-24" />
      <div className="rounded-xl border border-border">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 border-b border-border px-3 py-3 last:border-b-0">
            <Skeleton className="h-4 flex-1" />
            <Skeleton className="h-7 w-24" />
            <Skeleton className="h-7 w-36" />
          </div>
        ))}
      </div>
    </div>
  );
}
