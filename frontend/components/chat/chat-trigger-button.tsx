import { MessageCircle, X } from "lucide-react";
import { cn } from "@/lib/utils";

export function ChatTriggerButton({
  open,
  streaming,
  onClick,
}: {
  open: boolean;
  streaming: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={open ? "Close Jarvis" : "Open Jarvis"}
      className={cn(
        "flex h-12 w-12 items-center justify-center rounded-full bg-accent text-accent-foreground shadow-lg transition-transform hover:scale-105",
        streaming && !open && "ai-glow ai-glow--generating",
      )}
    >
      {open ? <X size={20} /> : <MessageCircle size={20} />}
    </button>
  );
}
