import { AppShell } from "@/components/layout/app-shell";
import { requireSession } from "@/lib/session";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const user = await requireSession();
  return <AppShell email={user.email}>{children}</AppShell>;
}
