import { AppShell } from "@/components/layout/app-shell";
import { requireSession } from "@/lib/session";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const user = await requireSession();
  const displayName = user.preferred_name || user.first_name;
  return (
    <AppShell displayName={displayName} email={user.email}>
      {children}
    </AppShell>
  );
}
