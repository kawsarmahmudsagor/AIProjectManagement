import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

// Extracted from components/ui/card.tsx (which re-exports this for existing
// `import { Card, Badge } from "@/components/ui/card"` call sites) — Badge earns its own
// file now that it has a real variant system instead of one fixed look.
type Variant = "neutral" | "accent" | "success" | "warning" | "danger" | "outline";

const VARIANTS: Record<Variant, string> = {
  neutral: "bg-surface-2 text-muted",
  accent: "bg-accent-subtle text-accent-solid border border-accent-line",
  success: "bg-success-subtle text-success-solid border border-success-line",
  warning: "bg-warning-subtle text-warning-solid border border-warning-line",
  danger: "bg-danger-subtle text-danger-solid border border-danger-line",
  outline: "border border-border text-muted",
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
}

export function Badge({ className, variant = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}
