import { CharacterCount } from "@tiptap/extension-character-count";
import { Placeholder } from "@tiptap/extension-placeholder";
import { StarterKit } from "@tiptap/starter-kit";
import { countPlain } from "@/lib/rich-text/count";

/**
 * Tiptap 3.x's StarterKit already bundles Underline, so no separate
 * @tiptap/extension-underline is installed — adding one directly here would register a
 * duplicate `underline` mark. We disable link/strike/codeBlock/blockquote/horizontalRule
 * since the mockup toolbar (Paragraph, B/I/U, both lists, clear formatting) has no
 * affordance for them — StarterKit keeps that surface intentionally narrow.
 */
export function buildExtensions({ limit, placeholder }: { limit: number; placeholder: string }) {
  return [
    StarterKit.configure({
      link: false,
      strike: false,
      codeBlock: false,
      code: false,
      blockquote: false,
      horizontalRule: false,
      heading: { levels: [1, 2, 3] },
    }),
    Placeholder.configure({ placeholder }),
    CharacterCount.configure({
      limit,
      mode: "textSize",
      textCounter: countPlain,
    }),
  ];
}
