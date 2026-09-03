"""_is_suggestable_technology() is what keeps recompute_user_suggestions from spending a
user's top-N suggestion slots on generic stack entries (Python, TypeScript, SQLAlchemy,
bare "Unity", ...) instead of the more specific/notable technologies (an LLM framework, a
RAG tool, a named Unity plugin) a repo suggestion is actually useful for.
"""

from app.services.suggestion_service import _is_suggestable_technology


def test_generic_stack_entries_are_filtered_out():
    for name in ["Python", "TypeScript", "Node.js", "SQLAlchemy", "SQL Alchemy", "Unity", "React", "Docker", "PostgreSQL"]:
        assert not _is_suggestable_technology(name), name


def test_specific_notable_entries_are_kept():
    for name in ["LangChain", "LangGraph", "RAG", "LLM", "AR Foundation", "MRTK", "Pipecat", "Diffusers"]:
        assert _is_suggestable_technology(name), name


def test_matching_is_case_and_whitespace_insensitive():
    assert not _is_suggestable_technology("  PYTHON  ")
    assert not _is_suggestable_technology("typescript")
