"use client";

import { File, Image as ImageIcon, Paperclip } from "lucide-react";
import { useRef } from "react";
import { IconButton } from "@/components/ui/icon-button";
import { Menu, MenuItem } from "@/components/ui/menu";
import { DOCUMENT_ACCEPT, IMAGE_ACCEPT } from "@/lib/chat-attachments";

/** Three separate hidden inputs, one per category — not one input whose `accept` is set
 * from state: `setAccept(x); inputRef.current.click()` in the same tick would click the
 * pre-update DOM node, since the accept attribute change and the click both happen
 * before React re-renders. Three inputs is boring and correct. */
export function ChatAttachMenu({ onFiles, disabled }: { onFiles: (files: File[]) => void; disabled?: boolean }) {
  const imageInputRef = useRef<HTMLInputElement>(null);
  const docInputRef = useRef<HTMLInputElement>(null);
  const anyInputRef = useRef<HTMLInputElement>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length) onFiles(files);
    e.target.value = "";
  };

  return (
    <>
      <Menu
        trigger={(triggerProps) => (
          <IconButton type="button" disabled={disabled} aria-label="Attach files" {...triggerProps}>
            <Paperclip size={16} />
          </IconButton>
        )}
        // The trigger sits at the bottom edge of the chat panel (composer is the last
        // element in an overflow-hidden column) — opening downward (Menu's default)
        // leaves no room and the panel gets clipped away entirely. Open upward instead.
        className="bottom-full top-auto mb-2 mt-0"
      >
        <MenuItem onClick={() => imageInputRef.current?.click()}>
          <ImageIcon size={14} /> Images
        </MenuItem>
        <MenuItem onClick={() => docInputRef.current?.click()}>
          <File size={14} /> Documents
        </MenuItem>
        <MenuItem onClick={() => anyInputRef.current?.click()}>
          <Paperclip size={14} /> Other
        </MenuItem>
      </Menu>
      <input ref={imageInputRef} type="file" multiple accept={IMAGE_ACCEPT} className="sr-only" onChange={handleChange} />
      <input ref={docInputRef} type="file" multiple accept={DOCUMENT_ACCEPT} className="sr-only" onChange={handleChange} />
      <input ref={anyInputRef} type="file" multiple className="sr-only" onChange={handleChange} />
    </>
  );
}
