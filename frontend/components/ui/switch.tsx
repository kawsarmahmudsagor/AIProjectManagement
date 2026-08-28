import { forwardRef } from "react";
import { cn } from "@/lib/utils";

export const Switch = forwardRef<
  HTMLButtonElement,
  {
    checked: boolean;
    onCheckedChange: (next: boolean) => void;
    disabled?: boolean;
    className?: string;
    "aria-label"?: string;
  }
>(function Switch({ checked, onCheckedChange, disabled, className, ...props }, ref) {
  return (
    <button
      ref={ref}
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border border-border transition-colors disabled:cursor-not-allowed disabled:opacity-60",
        checked ? "bg-accent" : "bg-surface-2",
        className,
      )}
      {...props}
    >
      <span
        aria-hidden="true"
        className={cn(
          "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
          checked ? "translate-x-6" : "translate-x-1",
        )}
      />
    </button>
  );
});
