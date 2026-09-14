from pydantic import BaseModel, Field

# The renderer (services/poster_renderer.py) only knows how to draw these — anything else
# the model emits is repaired to the default by normalize_poster_spec. Deliberately not a
# Python Enum on the Pydantic field: schema_utils.simplify_for_gemini strips `enum` from
# the schema handed to Gemini (see its docstring), so the model receives no hard
# constraint here regardless — the vocabulary is enforced entirely by the normalizer.
MOTIF_CHOICES = ("geometric", "waves", "grid", "diagonal", "circles", "blank")
DEFAULT_MOTIF = "geometric"
DEFAULT_PALETTE = ["#2f6fe0", "#eaf1fe", "#10131b"]


class LLMPosterSpec(BaseModel):
    """What the text model is asked to design when no image model is available — a small
    structured spec, not an image, that services/poster_renderer.py renders
    deterministically to SVG. Kept intentionally tiny: every field maps to something the
    renderer can actually draw, so there's no free-text field whose meaning the renderer
    would have to interpret."""

    palette: list[str] = Field(default_factory=lambda: list(DEFAULT_PALETTE))
    motif: str = DEFAULT_MOTIF
    headline: str = ""
