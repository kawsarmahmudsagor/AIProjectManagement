"""Server-side HTML handling for stored rich-text fields (backend/DESIGN.md §2, §7).

Three jobs live here:
1. html_to_text — recompute the plaintext used for char-cap validation. Never trust the
   client-supplied `text` half of a RichText pair.
2. sanitize_html — whitelist-clean HTML at save time so (a) the read-only detail view has
   no XSS surface and (b) html-for-docx (backend/render/docx.py) only ever sees markup it
   actually supports.
3. wrap_html — the reverse direction: deterministically turn LLM-authored plain text into
   paragraph HTML. The LLM never authors a RichText's html/text pair itself — every
   AI-writing path (ai_service.rewrite_field, extraction_service) produces plain text only
   and this function derives the html half in code.
"""

import re

import bleach

_ALLOWED_TAGS = [
    "p", "br", "strong", "b", "em", "i", "u", "s",
    "ul", "ol", "li", "a",
    "h1", "h2", "h3", "h4",
]
_ALLOWED_ATTRS = {"a": ["href", "title", "target", "rel"]}

_BLOCK_TAGS = re.compile(r"<(p|br|li|h[1-4])\b[^>]*>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t]+")


def sanitize_html(html: str) -> str:
    return bleach.clean(html or "", tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)


def html_to_text(html: str) -> str:
    """Strip tags -> plain text, inserting newlines at block boundaries so the character
    count roughly matches what Tiptap's `editor.getText({ blockSeparator: '\\n' })`
    produces client-side (frontend/DESIGN.md §1a)."""
    if not html:
        return ""
    with_breaks = _BLOCK_TAGS.sub("\n", html)
    text = _TAG.sub("", with_breaks)
    text = _WS.sub(" ", text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def wrap_html(plain_text: str | None) -> str:
    paragraphs = [p.strip() for p in (plain_text or "").split("\n") if p.strip()]
    return "".join(f"<p>{p}</p>" for p in paragraphs) or "<p></p>"
