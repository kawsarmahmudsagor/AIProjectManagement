"""The coupling test that makes hand-seeding app/search/app_features.py from
chat_app_guide.md safe: every `##` heading in the guide must be cited by at least one
registry entry's `guide_section`, so adding a feature to the guide without registering it
here fails loudly in CI instead of quietly becoming unsearchable.
"""

import re
from pathlib import Path

from app.search.app_features import APP_FEATURES

_GUIDE_PATH = Path(__file__).resolve().parent.parent / "app" / "agents" / "chat_app_guide.md"


def _guide_headings() -> list[str]:
    text = _GUIDE_PATH.read_text(encoding="utf-8")
    return re.findall(r"^## (.+)$", text, flags=re.MULTILINE)


def test_every_guide_heading_is_registered():
    registered_sections = {f.guide_section for f in APP_FEATURES}
    headings = _guide_headings()
    assert headings, "chat_app_guide.md has no ## headings — something is wrong with the fixture path"
    missing = [h for h in headings if h not in registered_sections]
    assert not missing, f"chat_app_guide.md sections with no app_features.py entry: {missing}"


def test_every_registered_section_actually_exists_in_the_guide():
    """The inverse check — catches a typo in guide_section that would otherwise silently
    make the coupling test above pass for the wrong reason."""
    headings = set(_guide_headings())
    for feature in APP_FEATURES:
        assert feature.guide_section in headings, f"{feature.slug}'s guide_section {feature.guide_section!r} doesn't match any heading"


def test_every_path_is_a_frontend_route():
    for feature in APP_FEATURES:
        assert feature.path.startswith("/"), f"{feature.slug}'s path {feature.path!r} must start with /"


def test_slugs_are_unique():
    slugs = [f.slug for f in APP_FEATURES]
    assert len(slugs) == len(set(slugs))


def test_every_entry_has_keywords():
    for feature in APP_FEATURES:
        assert feature.keywords, f"{feature.slug} has no keywords"
