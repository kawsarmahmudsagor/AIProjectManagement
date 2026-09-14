"""The SVG-poster fallback: a small LLM-designed spec (schemas.thumbnail.LLMPosterSpec)
rendered deterministically to an SVG "poster card" thumbnail when no image model is
available (providers.base.LLMProvider.generate_image raised IMAGE_GENERATION_UNSUPPORTED)
or one failed. Two halves, same discipline as breakdown_service.normalize_breakdown /
run_breakdown_job:

1. normalize_poster_spec() — repairs anything the model got wrong (an out-of-vocabulary
   motif, a malformed color, an overlong headline) and NEVER raises, exactly like
   normalize_breakdown's contract.
2. render_poster_svg() — pure, deterministic (same spec + seed -> byte-identical output
   twice) string templating. No dynamic/model-controlled markup structure: every model
   output that reaches the SVG string is (a) validated against a strict pattern first
   (palette colors) or (b) escaped via xml.sax.saxutils.escape (the headline) before
   interpolation, and never placed inside an unquoted attribute. The output deliberately
   contains no <script>, <image>, <foreignObject>, href, or @import — this is what
   makes it safe to serve under our own origin with only Content-Type +
   X-Content-Type-Options: nosniff (routers/project_media.py), even though user-uploaded
   SVG is never accepted (ingest/media_sniff.py's docstring) — this output is ours, an
   upload is not.
"""

import hashlib
import re
from xml.sax.saxutils import escape as _xml_escape

from app.providers.base import ThumbnailPromptInput
from app.schemas.thumbnail import DEFAULT_MOTIF, DEFAULT_PALETTE, MOTIF_CHOICES, LLMPosterSpec
from app.services.breakdown_service import _UNSAFE_CHARS_RE

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_MAX_HEADLINE_CHARS = 40
_MIN_PALETTE = 2
_MAX_PALETTE = 4

WIDTH = 1200
HEIGHT = 675


def normalize_poster_spec(raw: dict, ctx: ThumbnailPromptInput) -> LLMPosterSpec:
    """Repairs a raw LLM dict into a valid LLMPosterSpec — never raises. Any malformed
    field falls back to a safe default rather than rejecting the whole spec, matching
    breakdown_service.normalize_breakdown's "the model is a hostile, sloppy input source"
    posture."""
    if not isinstance(raw, dict):
        raw = {}

    palette_in = raw.get("palette")
    palette: list[str] = []
    if isinstance(palette_in, list):
        for v in palette_in:
            if isinstance(v, str) and _HEX_COLOR_RE.match(v.strip()):
                palette.append(v.strip())
            if len(palette) >= _MAX_PALETTE:
                break
    if len(palette) < _MIN_PALETTE:
        palette = list(DEFAULT_PALETTE)

    motif_in = raw.get("motif")
    motif = motif_in.strip().lower() if isinstance(motif_in, str) else DEFAULT_MOTIF
    if motif not in MOTIF_CHOICES:
        motif = DEFAULT_MOTIF

    headline_in = raw.get("headline")
    headline = headline_in.strip() if isinstance(headline_in, str) else ""
    if not headline:
        headline = ctx.name or ctx.role or ""
    # Strip control/zero-width/bidi-override characters — reuses
    # breakdown_service._UNSAFE_CHARS_RE directly rather than re-deriving the same
    # pattern, since this string is about to be drawn as visible text and a bidi
    # override is a cheap way to make it render differently than it reads in source.
    headline = _UNSAFE_CHARS_RE.sub("", headline)
    headline = headline[:_MAX_HEADLINE_CHARS].strip()

    return LLMPosterSpec(palette=palette, motif=motif, headline=headline)


def _seed_int(seed: object) -> int:
    digest = hashlib.sha256(str(seed).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _motif_shapes(motif: str, seed: int, fg: str, accent: str) -> str:
    """Returns the <g>...</g> decorative layer for one motif — plain shape primitives
    only (rect/circle/line/polygon), no <image>/<use xlink:href>/<foreignObject>."""
    if motif == "waves":
        paths = []
        for i in range(3):
            y = 420 + i * 60 + (seed >> (i * 4) & 15)
            paths.append(
                f'<path d="M0,{y} Q300,{y - 60} 600,{y} T1200,{y}" stroke="{accent}" '
                f'stroke-width="2" fill="none" opacity="{0.25 + i * 0.15:.2f}"/>'
            )
        return "".join(paths)
    if motif == "grid":
        lines = []
        for x in range(0, WIDTH + 1, 60):
            lines.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{HEIGHT}" stroke="{fg}" stroke-width="1" opacity="0.06"/>')
        for y in range(0, HEIGHT + 1, 60):
            lines.append(f'<line x1="0" y1="{y}" x2="{WIDTH}" y2="{y}" stroke="{fg}" stroke-width="1" opacity="0.06"/>')
        return "".join(lines)
    if motif == "diagonal":
        stripes = []
        for i in range(-2, 10):
            x = i * 140 + (seed % 60)
            stripes.append(
                f'<line x1="{x}" y1="0" x2="{x - 300}" y2="{HEIGHT}" stroke="{accent}" '
                f'stroke-width="40" opacity="0.08"/>'
            )
        return "".join(stripes)
    if motif == "circles":
        circles = []
        for i in range(6):
            cx = 100 + (i * 191 + seed) % (WIDTH - 200)
            cy = 100 + (i * 137 + seed) % (HEIGHT - 200)
            r = 40 + (i * 53 + seed) % 120
            circles.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{accent}" opacity="0.10"/>')
        return "".join(circles)
    if motif == "blank":
        return ""
    # "geometric" default: a handful of deterministically-placed rotated rects.
    rects = []
    for i in range(5):
        x = (i * 233 + seed) % WIDTH
        y = (i * 157 + seed) % HEIGHT
        size = 80 + (i * 41 + seed) % 160
        angle = (i * 37 + seed) % 360
        rects.append(
            f'<rect x="{x}" y="{y}" width="{size}" height="{size}" fill="{accent}" '
            f'opacity="0.10" transform="rotate({angle} {x + size / 2} {y + size / 2})"/>'
        )
    return "".join(rects)


def render_poster_svg(spec: LLMPosterSpec, *, seed: object) -> str:
    """Deterministic: the same (spec, seed) pair always renders byte-identical output —
    every "random" placement below is derived from a SHA-256 of `seed` (the project id),
    not from actual randomness, so two renders of the same project never visually drift
    against each other for no reason."""
    seed_int = _seed_int(seed)
    bg = spec.palette[0]
    fg = spec.palette[-1]
    accent = spec.palette[1] if len(spec.palette) > 1 else fg

    headline_safe = _xml_escape(spec.headline)
    shapes = _motif_shapes(spec.motif, seed_int, fg, accent)

    headline_block = ""
    if headline_safe:
        headline_block = (
            f'<text x="60" y="{HEIGHT - 70}" font-family="sans-serif" font-size="42" '
            f'font-weight="700" fill="{fg}">{headline_safe}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}">'
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{bg}"/>'
        f"<g>{shapes}</g>"
        f"{headline_block}"
        f"</svg>"
    )
