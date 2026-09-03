"""Guards the two structural properties Feature 2's design depends on:

1. The breakdown schema handed to a provider is genuinely flat (no $defs/$ref, shallow
   depth, no schema keywords outside the "verified supported" list) — see
   services/breakdown_service.py's _BREAKDOWN_SCHEMA and schemas/breakdown.py's docstring.
2. inline_refs() really does blow up on a self-referential schema, which is *why* the
   breakdown task tree is deliberately flat (parent_ref, not nested `subtasks`) rather
   than a comment someone can delete without consequence — see providers/schema_utils.py.
"""

import pytest
from pydantic import BaseModel

from app.providers.schema_utils import inline_refs, simplify_for_gemini
from app.schemas.breakdown import LLMBreakdownResult

_DISALLOWED_KEYWORDS = {"oneOf", "allOf", "pattern", "const", "uniqueItems"}


def _max_depth(node, depth=0) -> int:
    if isinstance(node, dict):
        if not node:
            return depth
        return max(_max_depth(v, depth + 1) for v in node.values())
    if isinstance(node, list):
        if not node:
            return depth
        return max(_max_depth(v, depth + 1) for v in node)
    return depth


def _collect_keys(node, keys: set) -> None:
    if isinstance(node, dict):
        keys.update(node.keys())
        for v in node.values():
            _collect_keys(v, keys)
    elif isinstance(node, list):
        for v in node:
            _collect_keys(v, keys)


def test_breakdown_schema_is_flat_with_no_refs():
    schema = inline_refs(LLMBreakdownResult.model_json_schema())
    assert "$defs" not in schema

    keys = set()
    _collect_keys(schema, keys)
    assert "$ref" not in keys


def test_breakdown_schema_depth_is_shallow():
    # Pydantic's own schema representation (object -> properties -> field -> type/title)
    # already costs several dict-traversal levels for even one flat field, so this bound
    # is generous on purpose — its job is to catch genuine runaway/recursive nesting, not
    # to pin an exact number. The no-$defs/no-$ref test above is what actually proves
    # flatness.
    schema = inline_refs(LLMBreakdownResult.model_json_schema())
    assert _max_depth(schema) <= 12


def test_breakdown_schema_uses_no_disallowed_keywords():
    schema = inline_refs(LLMBreakdownResult.model_json_schema())
    keys = set()
    _collect_keys(schema, keys)
    assert not (keys & _DISALLOWED_KEYWORDS)


def test_self_referential_schema_breaks_inline_refs():
    """Executable documentation for *why* the breakdown schema must never nest: a
    recursive Pydantic model makes inline_refs() recurse until Python's recursion limit
    trips, which at import time (as _BREAKDOWN_SCHEMA is a module-level constant) would
    take down both the API process and the SAQ worker — see schema_utils.py's docstring
    and backend/DESIGN.md's "verified fact #3"."""

    class RecursiveNode(BaseModel):
        title: str
        children: list["RecursiveNode"] = []

    RecursiveNode.model_rebuild()

    with pytest.raises(RecursionError):
        inline_refs(RecursiveNode.model_json_schema())


def test_simplify_for_gemini_strips_enum_and_max_items():
    # Live Gemini rejected the raw breakdown schema (400 INVALID_ARGUMENT) once a real key
    # was available to test against — the untested-in-production combination turned out to
    # be `enum` nested inside an `anyOf` null-union branch (estimate_size) plus a plain
    # `enum` (priority), neither of which appear in extraction's schema, the one schema
    # actually proven against the live API. Both are already repaired in
    # breakdown_service.normalize_breakdown() if the model emits an out-of-set value, so
    # dropping the schema-level constraint doesn't weaken validation.
    schema = simplify_for_gemini(inline_refs(LLMBreakdownResult.model_json_schema()))
    keys = set()
    _collect_keys(schema, keys)
    assert "enum" not in keys
    assert "maxItems" not in keys
    assert "minItems" not in keys


def test_simplify_for_gemini_keeps_types_and_null_unions():
    schema = simplify_for_gemini(inline_refs(LLMBreakdownResult.model_json_schema()))
    estimate_size = schema["properties"]["tasks"]["items"]["properties"]["estimate_size"]
    assert estimate_size["anyOf"] == [{"type": "string"}, {"type": "null"}]
