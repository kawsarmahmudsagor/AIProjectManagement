import { cn } from "@/lib/utils";
import { forwardRef, type SelectHTMLAttributes } from "react";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        "rounded-lg border border-border bg-background px-2 py-1.5 text-sm text-foreground",
        "focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent",
        className,
      )}
      {...props}
    />
  ),
);
Select.displayName = "Select";
