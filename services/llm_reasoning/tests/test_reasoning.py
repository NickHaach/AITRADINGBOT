"""Unit tests for LLM reasoning mock."""

import pytest

from llm_reasoning.engine import LLMReasoningEngine, MockLLM


@pytest.mark.asyncio
async def test_mock_llm_oil_event() -> None:
    engine = LLMReasoningEngine(MockLLM())
    result = await engine.reason(
        "OPEC+ discusses further oil production cuts amid Middle East tensions. Crude jumped."
    )
    assert "XOM" in result.beneficiaries or any("oil" in b.lower() for b in result.beneficiaries)
    assert 0 <= result.confidence <= 1
    assert result.expected_reaction
    assert result.risks
