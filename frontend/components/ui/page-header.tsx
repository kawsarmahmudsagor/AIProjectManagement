/** Every one of this app's ~16 routes hand-rolls the same
 * `<h1 className="text-2xl font-semibold">Title</h1>` + optional description + optional
 * right-aligned actions row (see app/(app)/dashboard/page.tsx, app/(app)/projects/page.tsx,
 * app/(app)/conversations/page.tsx, ...) — this collects that pattern into one component
 * so it stays visually consistent as the redesign lands page by page. */
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
