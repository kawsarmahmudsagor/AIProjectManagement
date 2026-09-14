"""Magic-byte format detection for images and video (app/ingest/media_sniff.py) — the
media counterpart to test_document_sniff.py."""

import pytest

from app.ingest.media_sniff import UnsupportedMediaFormatError, sniff_image_mime_type, sniff_video_mime_type


def test_png_recognized():
    assert sniff_image_mime_type(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16) == "image/png"


def test_jpeg_recognized():
    assert sniff_image_mime_type(b"\xff\xd8\xff" + b"\x00" * 16) == "image/jpeg"


def test_webp_recognized():
    data = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 8
    assert sniff_image_mime_type(data) == "image/webp"


def test_gif_rejected_as_image():
    with pytest.raises(UnsupportedMediaFormatError) as exc_info:
        sniff_image_mime_type(b"GIF89a" + b"\x00" * 16)
    assert exc_info.value.code == "unsupported_image_format"


def test_svg_never_accepted_as_upload():
    """SVG is our own trusted rendered output (services/poster_renderer.py), never
    something a user upload should be allowed to claim to be — active-content risk."""
    svg_bytes = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    with pytest.raises(UnsupportedMediaFormatError):
        sniff_image_mime_type(svg_bytes)


def test_truncated_input_does_not_crash():
    with pytest.raises(UnsupportedMediaFormatError):
        sniff_image_mime_type(b"\x89P")


def _mp4(brand: bytes) -> bytes:
    return b"\x00\x00\x00\x18ftyp" + brand + b"\x00" * 16


def test_mp4_isom_brand_recognized():
    assert sniff_video_mime_type(_mp4(b"isom")) == "video/mp4"


def test_mp4_mp42_brand_recognized():
    assert sniff_video_mime_type(_mp4(b"mp42")) == "video/mp4"


def test_mp4_avc1_brand_recognized():
    assert sniff_video_mime_type(_mp4(b"avc1")) == "video/mp4"


def test_quicktime_rejected_with_specific_code():
    with pytest.raises(UnsupportedMediaFormatError) as exc_info:
        sniff_video_mime_type(_mp4(b"qt  "))
    assert exc_info.value.code == "quicktime_unsupported"


def test_unknown_ftyp_brand_rejected():
    with pytest.raises(UnsupportedMediaFormatError) as exc_info:
        sniff_video_mime_type(_mp4(b"zzzz"))
    assert exc_info.value.code == "unsupported_video_format"


def _webm(doctype: bytes) -> bytes:
    return b"\x1a\x45\xdf\xa3" + b"\x00\x00\x00\x00" + doctype + b"\x00" * 16


def test_webm_doctype_recognized():
    assert sniff_video_mime_type(_webm(b"webm")) == "video/webm"


def test_matroska_rejected_with_specific_code():
    with pytest.raises(UnsupportedMediaFormatError) as exc_info:
        sniff_video_mime_type(_webm(b"matroska"))
    assert exc_info.value.code == "matroska_unsupported"


def test_jpeg_fed_to_video_sniffer_is_rejected():
    """Extension/claimed-type is never trusted — format comes from magic bytes only."""
    with pytest.raises(UnsupportedMediaFormatError):
        sniff_video_mime_type(b"\xff\xd8\xff" + b"\x00" * 16)


def test_truncated_video_input_does_not_crash():
    with pytest.raises(UnsupportedMediaFormatError):
        sniff_video_mime_type(b"\x00\x00")
