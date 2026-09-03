"""Inline Pydantic's `$defs`/`$ref` into a flat JSON Schema.

Both providers are safer with flattened schemas: Gemini's docs warn that "very large or
deeply nested schemas may be rejected," and OpenAI's Structured Outputs feature is
documented against flat, fully-resolved schemas rather than `$ref`-based ones. Pydantic's
`model_json_schema()` emits `$defs` by default for any nested model, so this runs on
every schema handed to a provider.
"""

import copy


def inline_refs(schema: dict) -> dict:
    defs = schema.get("$defs", {})
    if not defs:
        return schema

    def _resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                # Pydantic doesn't always emit a bare `{"$ref": ...}` — a field with a
                # default or description keeps those as siblings on the same node, e.g.
                # {"$ref": "#/$defs/X", "default": {...}}. Resolve the ref and layer the
                # siblings on top rather than requiring an exact one-key match.
                ref_name = node["$ref"].rsplit("/", 1)[-1]
                resolved = _resolve(copy.deepcopy(defs[ref_name]))
                siblings = {k: _resolve(v) for k, v in node.items() if k not in ("$ref", "$defs")}
                return {**resolved, **siblings}
            return {k: _resolve(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [_resolve(v) for v in node]
        return node

    result = _resolve(schema)
    result.pop("$defs", None)
    return result


def simplify_for_gemini(schema: dict) -> dict:
    """Strips `enum` and `maxItems`/`minItems` from an already-inlined schema before it goes
    to Gemini's `response_schema`/`response_json_schema`.

    docs/RESEARCH.md §A3's verified "supported schema surface" lists `enum` and `maxItems`
    as supported in isolation, but every construct this repo has actually exercised live
    (extraction's schema) uses neither — a plain top-level `enum` (breakdown's `priority`)
    and, worse, `enum` nested inside an `anyOf` null-union branch (breakdown's
    `estimate_size`) are both new and unverified combinations, and RESEARCH.md's own caveat
    is explicit: "UNVERIFIED individually — test yours." Both fields are already repaired
    in `services/breakdown_service.py::normalize_breakdown()` if the model emits something
    outside the allowed set (an unknown priority falls back to "medium", an unknown
    estimate_size falls back to None) — so relaxing the JSON-schema-level constraint here
    doesn't weaken validation, it just moves it to the layer that was already doing it.
    `maxItems` is dropped for the same reason: `max_tasks` is enforced both in the prompt
    and again in normalize_breakdown, so the schema-level cap is redundant, and it's the
    other construct with no precedent in a schema proven to work against the live API.
    OpenAI's schema is untouched — this only ever runs on the copy handed to Gemini.
    """

    def _strip(node):
        if isinstance(node, dict):
            return {
                k: _strip(v)
                for k, v in node.items()
                if k not in ("enum", "maxItems", "minItems")
            }
        if isinstance(node, list):
            return [_strip(v) for v in node]
        return node

    return _strip(schema)
