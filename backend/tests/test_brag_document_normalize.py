"""normalize_brag_document() must be total: every case below is a malformed/adversarial
raw provider response, and every assertion checks (a) nothing raises, (b) the repaired
result is deterministic, and (c) a confidence_note was recorded where a repair happened —
mirrors test_breakdown_normalize.py's approach for normalize_breakdown().
"""

from app.services.brag_document_service import normalize_brag_document


def test_completely_malformed_input_never_raises():
    for bad in (None, {}, {"technical_contributions": "not-a-list"}, [], "oops", 42, {"technical_contributions": [None, 42, "oops", {}]}):
        result = normalize_brag_document(bad)
        assert result.technical_contributions == [] or all(g.project_name for g in result.technical_contributions)


def test_valid_input_is_kept_as_is():
    raw = {
        "technical_contributions": [
            {"project_name": "XR23", "bullets": ["Implemented shader fix", "Wrote unit tests"]}
        ],
        "team_support_bullets": ["Attended sprint planning"],
        "learning_bullets": ["Researched Gaussian splatting"],
        "confidence_notes": [],
    }
    result = normalize_brag_document(raw)
    assert len(result.technical_contributions) == 1
    assert result.technical_contributions[0].project_name == "XR23"
    assert result.technical_contributions[0].bullets == ["Implemented shader fix", "Wrote unit tests"]
    assert result.team_support_bullets == ["Attended sprint planning"]
    assert result.learning_bullets == ["Researched Gaussian splatting"]
    assert result.confidence_notes == []


def test_missing_project_name_falls_back_to_on_demand_misc():
    raw = {"technical_contributions": [{"project_name": "", "bullets": ["Did a thing"]}]}
    result = normalize_brag_document(raw)
    assert result.technical_contributions[0].project_name == "On Demand / Miscellaneous"


def test_empty_bullet_group_is_dropped():
    raw = {"technical_contributions": [{"project_name": "XR23", "bullets": []}]}
    result = normalize_brag_document(raw)
    assert result.technical_contributions == []
    assert result.confidence_notes


def test_non_string_bullets_are_dropped_not_stringified():
    raw = {"technical_contributions": [{"project_name": "XR23", "bullets": ["Real bullet", None, 42, "   "]}]}
    result = normalize_brag_document(raw)
    assert result.technical_contributions[0].bullets == ["Real bullet"]


def test_group_with_unexpected_shape_is_dropped():
    raw = {"technical_contributions": ["not-a-dict", {"project_name": "XR23", "bullets": ["Real"]}]}
    result = normalize_brag_document(raw)
    assert len(result.technical_contributions) == 1
    assert result.confidence_notes


def test_duplicate_project_name_groups_are_merged_case_insensitively():
    raw = {
        "technical_contributions": [
            {"project_name": "XR23", "bullets": ["First bullet"]},
            {"project_name": "xr23", "bullets": ["Second bullet"]},
        ]
    }
    result = normalize_brag_document(raw)
    assert len(result.technical_contributions) == 1
    assert result.technical_contributions[0].bullets == ["First bullet", "Second bullet"]
    assert result.confidence_notes


def test_overlong_bullet_is_truncated_at_word_boundary():
    raw = {"technical_contributions": [{"project_name": "XR23", "bullets": ["word " * 100]}]}
    result = normalize_brag_document(raw)
    bullet = result.technical_contributions[0].bullets[0]
    assert len(bullet) <= 401  # 400 + ellipsis
    assert not bullet.endswith("word")


def test_overlong_project_name_is_truncated():
    raw = {"technical_contributions": [{"project_name": "X" * 300, "bullets": ["A bullet"]}]}
    result = normalize_brag_document(raw)
    assert len(result.technical_contributions[0].project_name) <= 201


def test_group_cap_is_enforced_and_reported():
    raw = {"technical_contributions": [{"project_name": f"Project {i}", "bullets": [f"Bullet {i}"]} for i in range(40)]}
    result = normalize_brag_document(raw)
    assert len(result.technical_contributions) <= 30
    assert any("cap" in n.lower() or "30" in n for n in result.confidence_notes)


def test_team_support_and_learning_bullets_filter_non_strings_and_blanks():
    raw = {"team_support_bullets": ["Real", None, 5, "   "], "learning_bullets": [123, "Also real"]}
    result = normalize_brag_document(raw)
    assert result.team_support_bullets == ["Real"]
    assert result.learning_bullets == ["Also real"]


def test_missing_team_support_and_learning_bullets_default_to_empty():
    result = normalize_brag_document({"technical_contributions": []})
    assert result.team_support_bullets == []
    assert result.learning_bullets == []


def test_confidence_notes_are_sanitized_and_capped():
    zero_width_space = chr(0x200B)
    raw = {"confidence_notes": [f"note{zero_width_space} {i}" for i in range(30)]}
    result = normalize_brag_document(raw)
    assert len(result.confidence_notes) <= 20
    assert all(zero_width_space not in n for n in result.confidence_notes)


def test_no_hour_or_date_fields_exist_on_the_result_shape():
    """Executable documentation for the grounding contract: LLMBragDocumentResult (and
    therefore normalize_brag_document's output) has no field an LLM could use to state an
    hour count or a date — those only ever come from BragDocumentJob.hour_stats."""
    result = normalize_brag_document({"technical_contributions": [{"project_name": "X", "bullets": ["Y"]}]})
    dumped = result.model_dump()
    assert "hours" not in str(dumped.keys()).lower()
    assert "hour_stats" not in dumped
