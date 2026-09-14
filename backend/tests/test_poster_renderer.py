"""services/poster_renderer.py — the SVG-poster fallback. normalize_poster_spec must
never raise regardless of how malformed the LLM's raw dict is (same contract as
breakdown_service.normalize_breakdown); render_poster_svg must be deterministic, produce
valid XML, and never let model-controlled text become markup.
"""

import xml.etree.ElementTree as ET

from app.providers.base import ThumbnailPromptInput
from app.schemas.thumbnail import DEFAULT_MOTIF, DEFAULT_PALETTE
from app.services.poster_renderer import normalize_poster_spec, render_poster_svg

_CTX = ThumbnailPromptInput(name="Test Project", role="Engineer")


def test_valid_spec_passes_through():
    spec = normalize_poster_spec({"palette": ["#112233", "#445566"], "motif": "waves", "headline": "Hello"}, _CTX)
    assert spec.palette == ["#112233", "#445566"]
    assert spec.motif == "waves"
    assert spec.headline == "Hello"


def test_none_input_repairs_to_defaults():
    spec = normalize_poster_spec(None, _CTX)
    assert spec.palette == list(DEFAULT_PALETTE)
    assert spec.motif == DEFAULT_MOTIF
    assert spec.headline == _CTX.name


def test_empty_dict_repairs_to_defaults():
    spec = normalize_poster_spec({}, _CTX)
    assert spec.palette == list(DEFAULT_PALETTE)
    assert spec.motif == DEFAULT_MOTIF


def test_malformed_palette_type_falls_back():
    spec = normalize_poster_spec({"palette": "not-a-list"}, _CTX)
    assert spec.palette == list(DEFAULT_PALETTE)


def test_too_few_valid_colors_falls_back():
    spec = normalize_poster_spec({"palette": ["#112233", "red", "not-a-color"]}, _CTX)
    assert spec.palette == list(DEFAULT_PALETTE)


def test_too_many_colors_capped():
    spec = normalize_poster_spec({"palette": ["#111111", "#222222", "#333333", "#444444", "#555555"]}, _CTX)
    assert len(spec.palette) == 4


def test_css_injection_palette_value_rejected():
    spec = normalize_poster_spec({"palette": ["#fff; } * { fill: black", "#112233"]}, _CTX)
    assert spec.palette == list(DEFAULT_PALETTE)
    for color in spec.palette:
        assert ";" not in color and "}" not in color


def test_unknown_motif_falls_back_to_default():
    spec = normalize_poster_spec({"motif": "sparkles"}, _CTX)
    assert spec.motif == DEFAULT_MOTIF


def test_overlong_headline_truncated():
    spec = normalize_poster_spec({"headline": "x" * 500}, _CTX)
    assert len(spec.headline) <= 40


def test_missing_headline_falls_back_to_project_name():
    spec = normalize_poster_spec({"headline": None}, _CTX)
    assert spec.headline == _CTX.name


def test_never_raises_on_garbage():
    garbage_inputs = [
        {},
        None,
        {"palette": None, "motif": None, "headline": None},
        {"palette": [1, 2, 3], "motif": 42, "headline": {"nested": "object"}},
        {"palette": []},
    ]
    for raw in garbage_inputs:
        normalize_poster_spec(raw, _CTX)  # must not raise


def test_render_is_deterministic():
    spec = normalize_poster_spec({"palette": ["#111111", "#222222"], "motif": "geometric"}, _CTX)
    svg1 = render_poster_svg(spec, seed="project-123")
    svg2 = render_poster_svg(spec, seed="project-123")
    assert svg1 == svg2


def test_different_seeds_can_differ():
    spec = normalize_poster_spec({"motif": "geometric"}, _CTX)
    svg1 = render_poster_svg(spec, seed="project-a")
    svg2 = render_poster_svg(spec, seed="project-b")
    assert svg1 != svg2  # geometric motif's shape placement is seed-derived


def test_output_parses_as_valid_xml():
    spec = normalize_poster_spec({"headline": "My Project"}, _CTX)
    svg = render_poster_svg(spec, seed=1)
    tree = ET.fromstring(svg)
    assert tree.tag.endswith("svg")


def test_viewbox_and_dimensions():
    spec = normalize_poster_spec({}, _CTX)
    svg = render_poster_svg(spec, seed=1)
    assert 'viewBox="0 0 1200 675"' in svg
    assert 'width="1200"' in svg
    assert 'height="675"' in svg


def test_script_injection_in_headline_is_escaped_not_executed():
    xss = normalize_poster_spec({"headline": '"><script>alert(1)</script>'}, _CTX)
    svg = render_poster_svg(xss, seed=1)
    assert "<script" not in svg
    tree = ET.fromstring(svg)  # must still parse — proves the injection didn't break structure
    for el in tree.iter():
        assert not el.tag.endswith("script")


def test_output_never_contains_dangerous_constructs():
    for motif in ("geometric", "waves", "grid", "diagonal", "circles", "blank"):
        spec = normalize_poster_spec({"motif": motif, "headline": "Some Project"}, _CTX)
        svg = render_poster_svg(spec, seed=motif)
        assert "<image" not in svg
        assert "foreignObject" not in svg
        assert "href" not in svg
        assert "@import" not in svg
        assert "<script" not in svg
