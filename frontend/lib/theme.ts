export type ThemeChoice = "light" | "dark" | "system";

export const THEME_COOKIE = "aipm_theme";
const THEME_MAX_AGE = 365 * 24 * 60 * 60; // a year — this is a preference, not a session

export function parseThemeCookie(value: string | undefined): ThemeChoice {
  return value === "light" || value === "dark" ? value : "system";
}

/** The attribute app/layout.tsx stamps onto <html> — `null` for "system" so the page
 * falls through to the `@media (prefers-color-scheme: dark)` block in globals.css
 * instead of pinning either theme. This is what makes the toggle "win" over the OS
 * setting when explicit, while leaving the OS in control by default (see
 * globals.css's token-block comment on the two dark overrides). */
export function themeDataAttr(choice: ThemeChoice): "light" | "dark" | undefined {
  return choice === "system" ? undefined : choice;
}

export { THEME_MAX_AGE };
