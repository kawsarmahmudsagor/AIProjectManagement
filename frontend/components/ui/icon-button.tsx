import { forwardRef } from "react";
import { Button, type ButtonProps } from "@/components/ui/button";

/** Thin wrapper over Button with iconOnly pre-set — most icon-only call sites (nav
 * collapse toggle, chat panel header actions, delete buttons) want `variant="ghost"` by
 * default too, unlike Button's own default of "primary". */
export const IconButton = forwardRef<HTMLButtonElement, Omit<ButtonProps, "iconOnly">>(
  function IconButton({ variant = "ghost", ...props }, ref) {
    return <Button ref={ref} variant={variant} iconOnly {...props} />;
  },
);
