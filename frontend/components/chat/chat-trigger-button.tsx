import { MessageCircle } from "lucide-react";
import { cn } from "@/lib/utils";

/** Only ever rendered while the panel is closed (chat-widget.tsx) — docked/overlay/
 * fullscreen presentations all have their own header close button once open, so this no
 * longer needs to swap its icon to an X or track `open` itself. */
export function ChatTriggerButton({ streaming, onClick }: { streaming: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Open Jarvis"
      className={cn(
        "flex h-12 w-12 items-center justify-center rounded-full bg-accent text-accent-foreground shadow-elevation-2 transition-transform hover:scale-105",
        streaming && "ai-glow ai-glow--generating",
      )}
    >
      <MessageCircle size={20} />
    </button>
  );
}
