import { cn } from "@/lib/utils";
import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-accent-foreground hover:bg-accent/90 disabled:bg-accent/40",
  secondary: "bg-surface-2 text-foreground border border-border hover:bg-surface-2/70",
  ghost: "text-foreground hover:bg-surface-2",
  danger: "bg-danger text-white hover:bg-danger/90",
};

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }>(
  function Button({ variant = "primary", className, ...props }, ref) {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60",
          VARIANTS[variant],
          className,
        )}
        {...props}
      />
    );
  },
);
