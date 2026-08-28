"""Inline Pydantic's `$defs`/`$ref` into a flat JSON Schema.

Both providers are safer with flattened schemas: Ollama has a documented history of
`$ref`-ordering bugs (docs/RESEARCH.md §B2), and Gemini's docs warn that "very large or
deeply nested schemas may be rejected." Pydantic's `model_json_schema()` emits `$defs`
by default for any nested model, so this runs on every schema handed to a provider.
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
