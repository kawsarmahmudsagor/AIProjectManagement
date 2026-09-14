"""The one place a multimodal chat human message's content blocks are built.

The two adapters use *different* dialects for inline binary data in this codebase's own
verified call shapes: `{"type": "media", "mime_type", "data"}` for Gemini
(providers/gemini.py's extract()/propose_breakdown()) versus `{"type": "file",
"source_type": "base64", "mime_type", "data", "filename"}` for OpenAI (providers/
openai.py's equivalents). That divergence lives inside each adapter today because each
dialect is only ever used there. Chat is different: services/chat_service.py builds ONE
HumanMessage that then flows through agents/chatbot_graph.py into whichever provider the
user has configured, so the dialect can't be chosen inside either adapter — it has to be
chosen here, outside both.

Images use LangChain's standard image block for both providers:
    {"type": "image", "source_type": "base64", "mime_type": ..., "data": <b64>}
This is the one block shape nothing else in this codebase emits (only the PDF-shaped
media/file blocks are exercised elsewhere) — verify it against a live call per provider
before trusting it in production; tests/test_chat_attachments.py pins the shape emitted
here so a langchain-core upgrade that changes it fails loudly in this module instead of
silently degrading a chat turn to text-only.

Document attachments are NOT binary blocks at all — they were extracted to text at
upload time (services/chat_service.save_attachment) and are injected as delimited text
blocks, which every model handles identically and costs nothing to replay.
"""

import base64
from dataclasses import dataclass
from uuid import UUID

from app.models.chat_attachment import AttachmentKind


@dataclass(frozen=True)
class AttachmentPayload:
    id: UUID
    filename: str
    mime_type: str
    kind: AttachmentKind
    data: bytes | None = None  # images only
    extracted_text: str | None = None  # documents only
    text_truncated: bool = False


def image_placeholder_block(filename: str) -> dict:
    """Stands in for an image dropped by chat_service's _MAX_REPLAYED_IMAGES cap, so the
    model still knows an image was there rather than seeing a hole in the conversation."""
    return {"type": "text", "text": f'[image "{filename}" was attached earlier in this conversation]'}


def build_user_content(text: str, attachments: list[AttachmentPayload]) -> str | list[dict]:
    """Returns a plain `str` when there are no attachments — byte-for-byte identical to
    the pre-attachments `HumanMessage(content=user_message)` call — so the overwhelmingly
    common no-attachment path cannot regress.

    Ordering is deliberate: attachment blocks first, the user's own text LAST, so the
    actual question is the final thing the model reads. The `--- Attached file: ... ---`
    delimiters are matched by a line in build_chatbot_system_prompt telling the model to
    treat delimited content as user-supplied DATA, never as instructions.
    """
    if not attachments:
        return text

    blocks: list[dict] = []
    for a in attachments:
        if a.kind == AttachmentKind.IMAGE and a.data:
            blocks.append(
                {
                    "type": "image",
                    "source_type": "base64",
                    "mime_type": a.mime_type,
                    "data": base64.b64encode(a.data).decode(),
                }
            )
        elif a.extracted_text:
            suffix = "\n[truncated]" if a.text_truncated else ""
            blocks.append(
                {
                    "type": "text",
                    "text": (
                        f"--- Attached file: {a.filename} ---\n{a.extracted_text}{suffix}\n"
                        f"--- end of {a.filename} ---"
                    ),
                }
            )
        else:
            blocks.append({"type": "text", "text": f"--- Attached file: {a.filename} (no text could be extracted) ---"})
    blocks.append({"type": "text", "text": text})
    return blocks
