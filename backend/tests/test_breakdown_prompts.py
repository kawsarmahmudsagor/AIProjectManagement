"""BREAKDOWN_SYSTEM_PROMPTS is the load-bearing safety surface for Feature 2 (backend/
DESIGN.md §8): every persona must carry the same grounding contract and the same shared
safety boundary, since the persona only changes tone, never the honesty guarantees.
"""

from app.models.user import AgentPersona
from app.providers.prompts import AGENT_SAFETY_BOUNDARIES, BREAKDOWN_SYSTEM_PROMPTS


def test_every_persona_has_a_breakdown_prompt():
    assert set(BREAKDOWN_SYSTEM_PROMPTS.keys()) == set(AgentPersona)


def test_every_breakdown_prompt_ends_with_safety_boundaries():
    for prompt in BREAKDOWN_SYSTEM_PROMPTS.values():
        assert prompt.endswith(AGENT_SAFETY_BOUNDARIES)


def test_every_breakdown_prompt_states_the_grounding_rule():
    for prompt in BREAKDOWN_SYSTEM_PROMPTS.values():
        assert "verbatim" in prompt.lower()
        assert "source_quote" in prompt
        assert "grounded=false" in prompt.lower() or "grounded = false" in prompt.lower()


def test_every_breakdown_prompt_prohibits_due_dates():
    for prompt in BREAKDOWN_SYSTEM_PROMPTS.values():
        assert "due-date" in prompt.lower() or "due date" in prompt.lower()
        assert "no due" in prompt.lower() or "there is no due" in prompt.lower()
