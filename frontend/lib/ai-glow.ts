/** Shared type for the app's one AI-affordance visual language — the animated
 * conic-gradient ring defined in app/globals.css (`.ai-glow`, `.ai-glow--generating`,
 * `.ai-glow--applied`). Originally declared inside rich-text-editor.tsx (the first
 * surface to use it); moved here so non-editor surfaces (the project thumbnail
 * generator, the dashboard search "ask Jarvis" row) can share the same type without
 * importing from an editor-specific module. Re-exported from rich-text-editor.tsx so
 * existing imports of `AiGlowState` from there keep working unchanged. */
export type AiGlowState = "idle" | "generating" | "applied";
