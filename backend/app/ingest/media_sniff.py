"""Magic-byte format detection for images and video — the media counterpart to
ingest/extract.sniff_mime_type (which covers PDF/DOCX/XLSX/text and deliberately
*rejects* images). Same rule as that module's docstring: format comes from magic bytes,
never from the client-supplied filename or Content-Type.

Note the deliberate asymmetry with what we *serve*: an AI-generated poster thumbnail is
stored as image/svg+xml (services/poster_renderer.py), but SVG is never accepted from an
upload — it's an active-content format (script, external refs, XXE) and accepting one
would put attacker-controlled markup behind a same-origin URL.
"""

_IMAGE_MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
}
# MP4-family brands we're willing to serve to a browser <video>. 'qt  ' (QuickTime) and
# Matroska are recognized-but-rejected below so the error names the real problem instead
# of falling through to "unrecognized".
_MP4_BRANDS = {
    b"isom", b"iso2", b"iso4", b"iso5", b"iso6", b"mp41", b"mp42", b"avc1", b"mp4v",
    b"dash", b"M4V ",
}
_EBML_MAGIC = b"\x1a\x45\xdf\xa3"


class UnsupportedMediaFormatError(Exception):
    """Carries code+message like ingest.extract.UnsupportedFormatError so routers can
    return the same {"code","message"} 415 body (routers/documents.py:39-40)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def sniff_image_mime_type(data: bytes) -> str:
    for magic, mime in _IMAGE_MAGIC.items():
        if data.startswith(magic):
            return mime
    if data[:12] and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise UnsupportedMediaFormatError(
        "unsupported_image_format", "Only JPEG, PNG, or WEBP images are supported."
    )


def sniff_video_mime_type(data: bytes) -> str:
    """MP4 family: bytes 4..8 are the 'ftyp' box type, 8..12 the brand. WebM: an EBML
    header whose DocType ("webm"/"matroska") appears in the first chunk of bytes."""
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in _MP4_BRANDS:
            return "video/mp4"
        if brand == b"qt  ":
            raise UnsupportedMediaFormatError(
                "quicktime_unsupported",
                "QuickTime (.mov) files don't play reliably in browsers — please export "
                "as MP4 (H.264) or WebM and upload again.",
            )
        raise UnsupportedMediaFormatError(
            "unsupported_video_format", "Only MP4 (H.264) and WebM videos are supported."
        )
    if data.startswith(_EBML_MAGIC):
        head = data[:64]
        if b"webm" in head:
            return "video/webm"
        if b"matroska" in head:
            raise UnsupportedMediaFormatError(
                "matroska_unsupported",
                "Matroska (.mkv) files don't play in browsers — please export as MP4 "
                "(H.264) or WebM and upload again.",
            )
    raise UnsupportedMediaFormatError(
        "unsupported_video_format", "Only MP4 (H.264) and WebM videos are supported."
    )


__all__ = ["sniff_image_mime_type", "sniff_video_mime_type", "UnsupportedMediaFormatError"]
