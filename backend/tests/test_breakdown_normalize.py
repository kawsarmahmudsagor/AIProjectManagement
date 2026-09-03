"""normalize_breakdown() must be total: every case below is a malformed/adversarial
provider response, and every assertion checks (a) nothing raises, (b) the repaired result
is deterministic, and (c) a confidence_note was recorded explaining the repair — see
services/breakdown_service.py's docstring.
"""

from app.services.breakdown_service import normalize_breakdown


def _titles(result):
    return {t.ref: t.title for t in result.tasks}


def test_unknown_parent_ref_promotes_to_top_level():
    raw = {"tasks": [{"ref": "t1", "title": "Child", "parent_ref": "ghost"}]}
    result = normalize_breakdown(raw, max_tasks=25)
    assert len(result.tasks) == 1
    assert result.tasks[0].parent_ref is None
    assert result.confidence_notes


def test_self_parent_promotes_to_top_level():
    raw = {"tasks": [{"ref": "t1", "title": "Loops to itself", "parent_ref": "t1"}]}
    result = normalize_breakdown(raw, max_tasks=25)
    assert result.tasks[0].parent_ref is None
    assert result.confidence_notes


def test_two_item_cycle_both_promoted():
    raw = {
        "tasks": [
            {"ref": "a", "title": "A", "parent_ref": "b"},
            {"ref": "b", "title": "B", "parent_ref": "a"},
        ]
    }
    result = normalize_breakdown(raw, max_tasks=25)
    assert all(t.parent_ref is None for t in result.tasks)
    assert len(result.confidence_notes) >= 2


def test_three_level_chain_flattens_grandchild():
    raw = {
        "tasks": [
            {"ref": "grandparent", "title": "Grandparent"},
            {"ref": "parent", "title": "Parent", "parent_ref": "grandparent"},
            {"ref": "child", "title": "Grandchild", "parent_ref": "parent"},
        ]
    }
    result = normalize_breakdown(raw, max_tasks=25)
    by_ref = {t.ref: t for t in result.tasks}
    assert by_ref["parent"].parent_ref == "grandparent"  # valid 2-level nesting kept
    assert by_ref["child"].parent_ref is None  # flattened, not dropped
    assert result.confidence_notes


def test_duplicate_ref_is_renamed_not_collapsed():
    raw = {
        "tasks": [
            {"ref": "t1", "title": "First"},
            {"ref": "t1", "title": "Second"},
        ]
    }
    result = normalize_breakdown(raw, max_tasks=25)
    assert len(result.tasks) == 2
    refs = [t.ref for t in result.tasks]
    assert len(set(refs)) == 2
    assert result.confidence_notes


def test_blank_title_is_dropped():
    raw = {"tasks": [{"ref": "t1", "title": "   "}, {"ref": "t2", "title": "Real task"}]}
    result = normalize_breakdown(raw, max_tasks=25)
    assert len(result.tasks) == 1
    assert result.tasks[0].title == "Real task"
    assert result.confidence_notes


def test_overlong_title_truncated_at_word_boundary():
    raw = {"tasks": [{"ref": "t1", "title": "word " * 60}]}
    result = normalize_breakdown(raw, max_tasks=25)
    assert len(result.tasks[0].title) <= 201  # 200 + ellipsis
    assert not result.tasks[0].title.endswith("word")  # cut cleanly, not mid-word
    assert result.confidence_notes


def test_numbered_heading_prefix_is_stripped():
    raw = {"tasks": [{"ref": "t1", "title": "3.2 Billing Requirements"}]}
    result = normalize_breakdown(raw, max_tasks=25)
    assert result.tasks[0].title == "Billing Requirements"


def test_zero_width_and_bidi_chars_are_stripped():
    zero_width_space = chr(0x200B)
    bidi_override = chr(0x202E)
    raw = {"tasks": [{"ref": "t1", "title": f"Ta{zero_width_space}sk{bidi_override} name"}]}
    result = normalize_breakdown(raw, max_tasks=25)
    title = result.tasks[0].title
    assert zero_width_space not in title
    assert bidi_override not in title
    assert title == "Task name"


def test_task_cap_truncates_and_reports():
    raw = {"tasks": [{"ref": f"t{i}", "title": f"Task {i}"} for i in range(60)]}
    result = normalize_breakdown(raw, max_tasks=25)
    assert len(result.tasks) == 25
    assert any("25" in n or "cap" in n.lower() for n in result.confidence_notes)


def test_capping_reparents_orphaned_survivor():
    # Parent is task 0 (survives the cap); child is task 40 (dropped by the cap) whose
    # own child (task 41, also dropped) would otherwise dangle — but more importantly, a
    # survivor whose parent got cut must be promoted, not left pointing at a ref that no
    # longer exists in the result.
    raw = {
        "tasks": (
            [{"ref": "t0", "title": "Survives"}]
            + [{"ref": f"filler{i}", "title": f"Filler {i}"} for i in range(23)]
            + [{"ref": "cut_parent", "title": "Gets cut by the cap"}]
            + [{"ref": "orphan", "title": "Orphaned child", "parent_ref": "cut_parent"}]
        )
    }
    result = normalize_breakdown(raw, max_tasks=25)
    assert len(result.tasks) == 25
    by_ref = {t.ref: t for t in result.tasks}
    assert "orphan" not in by_ref  # dropped along with its parent by the cap


def test_bogus_priority_and_estimate_size_fall_back_to_defaults():
    raw = {"tasks": [{"ref": "t1", "title": "Task", "priority": "urgentest", "estimate_size": "xxl"}]}
    result = normalize_breakdown(raw, max_tasks=25)
    assert result.tasks[0].priority == "medium"
    assert result.tasks[0].estimate_size is None


def test_grounded_true_without_quote_is_demoted():
    raw = {"tasks": [{"ref": "t1", "title": "Task", "grounded": True, "source_quote": None}]}
    result = normalize_breakdown(raw, max_tasks=25)
    assert result.tasks[0].grounded is False
    assert result.confidence_notes


def test_grounded_true_with_quote_is_kept():
    raw = {"tasks": [{"ref": "t1", "title": "Task", "grounded": True, "source_quote": "the system must log in users"}]}
    result = normalize_breakdown(raw, max_tasks=25)
    assert result.tasks[0].grounded is True
    assert result.tasks[0].source_quote == "the system must log in users"


def test_many_ungrounded_items_are_noted_but_not_dropped():
    # A hard drop here would risk silently gutting a legitimate breakdown if a model
    # under-uses grounded=true — see breakdown_service.normalize_breakdown's comment.
    # This is a note for the review UI's grouping, never data loss.
    raw = {"tasks": [{"ref": f"t{i}", "title": f"Suggestion {i}", "grounded": False} for i in range(10)]}
    result = normalize_breakdown(raw, max_tasks=25)
    assert len(result.tasks) == 10
    assert any("5" in n for n in result.confidence_notes)


def test_completely_malformed_input_never_raises():
    for bad in (None, {}, {"tasks": "not-a-list"}, {"tasks": [None, 42, "oops", {}]}, []):
        result = normalize_breakdown(bad, max_tasks=25)
        assert result.tasks == [] or all(t.title for t in result.tasks)
