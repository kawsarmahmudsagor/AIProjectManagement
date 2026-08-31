import Link from "next/link";
import { Card } from "@/components/ui/card";
import type { ChatSession } from "@/lib/chat";

function formatTimestamp(iso: string) {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function RecentConversationsCard({ sessions }: { sessions: ChatSession[] }) {
  return (
    <Link href="/conversations">
      <Card className="h-full transition-colors hover:border-accent/60">
        <h3 className="font-semibold">Conversations</h3>
        {sessions.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No conversations with Jarvis yet.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {sessions.map((session) => (
              <li key={session.id} className="flex items-center justify-between gap-3 text-sm">
                <span className="truncate text-foreground/90">{session.title}</span>
                <span className="shrink-0 text-xs text-muted">{formatTimestamp(session.last_message_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </Link>
  );
}
