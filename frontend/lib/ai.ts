import { apiFetch } from "@/lib/api-client";
import type { RichText } from "@/lib/rich-text/types";

export type AiEnhanceOp = "enhance-long" | "generate-short" | "enhance-short";
export type ProjectSectionKey = "description" | "responsibilities";

/** Surrounding project fields sent alongside a box's own text so the rewrite reads
 * naturally next to the rest of the entry, rather than being generated in a vacuum —
 * see backend/app/schemas/ai_settings.py RewriteContext. */
export type AiRewriteContext = {
  project_name?: string;
  role?: string;
  technologies?: string[];
};

export async function requestAiRewrite(args: {
  op: AiEnhanceOp;
  section: ProjectSectionKey;
  target: RichText;
  source: RichText;
  context?: AiRewriteContext;
  /** Free-text ask the user typed for this one click (e.g. "focus on the model training
   * pipeline work"), via the enhance context prompt — see AiEnhanceContextDialog. Left
   * undefined/empty when the user submits without typing anything, in which case the
   * rewrite behaves exactly as it did before this option existed. */
  instruction?: string;
  signal?: AbortSignal;
}): Promise<RichText> {
  const result = await apiFetch<{ html: string; text: string }>("ai/rewrite", {
    method: "POST",
    signal: args.signal,
    body: JSON.stringify({
      op: args.op,
      section: args.section,
      target_html: args.target.html,
      source_html: args.source.html,
      context: args.context,
      instruction: args.instruction || undefined,
    }),
  });
  return result;
}
