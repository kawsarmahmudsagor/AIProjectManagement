import Link from "next/link";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold">Settings</h1>
      <div className="mb-6 flex gap-4 border-b border-border text-sm">
        <Link href="/settings/ai-providers" className="border-b-2 border-accent px-1 pb-2 text-foreground">
          AI Providers
        </Link>
      </div>
      {children}
    </div>
  );
}
