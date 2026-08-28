import { cn } from "@/lib/utils";
import { forwardRef, type InputHTMLAttributes } from "react";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted",
        "focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";
