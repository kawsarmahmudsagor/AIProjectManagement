"use client";

import { useEditorState, type Editor } from "@tiptap/react";
import { Bold, Italic, Underline, List, ListOrdered, Loader2, RemoveFormatting, Sparkles, Wand2 } from "lucide-react";
import { cn } from "@/lib/utils";

type BlockType = "paragraph" | "h1" | "h2" | "h3";

/** An AI action rendered as an icon button in the toolbar's top-right corner — the
 * production pattern for "enhance this box" triggers (an icon embedded in the text
 * area's own toolbar, e.g. SAP Fiori's AI Writing Assistant, Notion AI's inline prompt
 * menu): never overwrites directly, the caller is expected to show a suggestion the user
 * accepts or discards (see AiSuggestionPanel). */
export interface ToolbarAiAction {
  key: string;
  label: string;
  icon: "sparkles" | "wand";
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
}

const BLOCK_LABELS: Record<BlockType, string> = {
  paragraph: "Paragraph",
  h1: "Heading 1",
  h2: "Heading 2",
  h3: "Heading 3",
};

function ToolbarButton({
  active,
  onClick,
  label,
  children,
}: {
  active?: boolean;
  onClick: () => void;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={active}
      onMouseDown={(e) => e.preventDefault()} // keep editor selection/focus on click
      onClick={onClick}
      className={cn(
        "flex h-7 w-7 items-center justify-center rounded text-muted hover:bg-surface-2 hover:text-foreground",
        active && "bg-surface-2 text-accent",
      )}
    >
      {children}
    </button>
  );
}

const AI_ICONS = { sparkles: Sparkles, wand: Wand2 } as const;

function AiActionButton({ action }: { action: ToolbarAiAction }) {
  const Icon = AI_ICONS[action.icon];
  return (
    <button
      type="button"
      title={action.label}
      aria-label={action.label}
      onMouseDown={(e) => e.preventDefault()}
      onClick={action.onClick}
      disabled={action.disabled || action.loading}
      className={cn(
        "flex h-7 items-center gap-1 rounded px-1.5 text-xs font-medium text-accent hover:bg-accent/10",
        "disabled:cursor-not-allowed disabled:opacity-40",
      )}
    >
      {action.loading ? <Loader2 size={13} className="animate-spin" /> : <Icon size={13} />}
      <span className="hidden sm:inline">{action.label}</span>
    </button>
  );
}

export function EditorToolbar({ editor, aiActions }: { editor: Editor; aiActions?: ToolbarAiAction[] }) {
  const state = useEditorState({
    editor,
    selector: ({ editor: e }) => ({
      isBold: e.isActive("bold"),
      isItalic: e.isActive("italic"),
      isUnderline: e.isActive("underline"),
      isBulletList: e.isActive("bulletList"),
      isOrderedList: e.isActive("orderedList"),
      blockType: (e.isActive("heading", { level: 1 })
        ? "h1"
        : e.isActive("heading", { level: 2 })
          ? "h2"
          : e.isActive("heading", { level: 3 })
            ? "h3"
            : "paragraph") as BlockType,
    }),
  });

  const setBlockType = (value: BlockType) => {
    const chain = editor.chain().focus();
    if (value === "paragraph") chain.setParagraph().run();
    else chain.setHeading({ level: Number(value[1]) as 1 | 2 | 3 }).run();
  };

  return (
    <div className="flex items-center gap-1 border-b border-border bg-surface-2/50 px-2 py-1.5">
      <select
        value={state.blockType}
        onChange={(e) => setBlockType(e.target.value as BlockType)}
        className="mr-1 rounded border border-border bg-background px-2 py-1 text-xs text-foreground focus:outline-none"
      >
        {Object.entries(BLOCK_LABELS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>

      <div className="mx-1 h-5 w-px bg-border" />

      <ToolbarButton label="Bold" active={state.isBold} onClick={() => editor.chain().focus().toggleBold().run()}>
        <Bold size={15} />
      </ToolbarButton>
      <ToolbarButton label="Italic" active={state.isItalic} onClick={() => editor.chain().focus().toggleItalic().run()}>
        <Italic size={15} />
      </ToolbarButton>
      <ToolbarButton
        label="Underline"
        active={state.isUnderline}
        onClick={() => editor.chain().focus().toggleUnderline().run()}
      >
        <Underline size={15} />
      </ToolbarButton>

      <div className="mx-1 h-5 w-px bg-border" />

      <ToolbarButton
        label="Bullet list"
        active={state.isBulletList}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
      >
        <List size={15} />
      </ToolbarButton>
      <ToolbarButton
        label="Ordered list"
        active={state.isOrderedList}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
      >
        <ListOrdered size={15} />
      </ToolbarButton>

      <div className="mx-1 h-5 w-px bg-border" />

      <ToolbarButton
        label="Clear formatting"
        onClick={() => editor.chain().focus().clearNodes().unsetAllMarks().run()}
      >
        <RemoveFormatting size={15} />
      </ToolbarButton>

      {aiActions && aiActions.length > 0 && (
        <div className="ml-auto flex items-center gap-0.5 pl-1">
          {aiActions.map((action) => (
            <AiActionButton key={action.key} action={action} />
          ))}
        </div>
      )}
    </div>
  );
}
