import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

// Colors deliberately still reference the original alias classes (bg-accent,
// text-foreground, bg-surface-2, border-border, bg-danger, ...) rather than the new
// --color-accent-solid/--color-ink/etc. tokens directly — both resolve to the exact same
// CSS variables today (see globals.css's back-compat alias block), so this file doesn't
// need to change again when the alias layer is eventually retired; only globals.css does.
const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-accent-foreground hover:bg-accent/90 disabled:bg-accent/40",
  secondary: "bg-surface-2 text-foreground border border-border hover:bg-surface-2/70",
  ghost: "text-foreground hover:bg-surface-2",
  danger: "bg-danger text-white hover:bg-danger/90",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-xs gap-1.5 rounded-md",
  md: "h-9 px-4 text-sm gap-2 rounded-lg",
  lg: "h-11 px-5 text-base gap-2 rounded-lg",
};

const ICON_ONLY_SIZES: Record<Size, string> = {
  sm: "h-8 w-8 p-0",
  md: "h-9 w-9 p-0",
  lg: "h-11 w-11 p-0",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  /** Removes horizontal padding and forces a square hit area for the size — the
   * encapsulated version of the `className="h-9 w-9 shrink-0 p-0"` override that used to
   * be hand-repeated at every icon-only call site (chat-composer.tsx, delete buttons,
   * the chat panel header, ...). */
  iconOnly?: boolean;
  /** Shows a spinner in place of the button's own icon/text and forces `disabled` — a
   * single flag instead of every call site writing its own
   * `{isSubmitting ? "Saving…" : "Save"}` ternary AND a separate `disabled={isSubmitting}`. */
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", iconOnly = false, loading = false, className, disabled, children, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex items-center justify-center font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60",
        VARIANTS[variant],
        iconOnly ? ICON_ONLY_SIZES[size] : SIZES[size],
        className,
      )}
      {...props}
    >
      {loading && <Loader2 size={size === "sm" ? 13 : size === "lg" ? 18 : 15} className="animate-spin" />}
      {!loading && children}
    </button>
  );
});
