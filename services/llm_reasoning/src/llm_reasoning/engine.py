"""LLM Reasoning Engine — structured market-impact explanations."""

from __future__ import annotations

import json
import re
from typing import Protocol

from ai_trading_shared.domain.entities import LLMReasoningResult


class LLMPort(Protocol):
    async def complete_json(self, system: str, user: str) -> dict:
        ...


SYSTEM_PROMPT = """You are a hedge-fund research analyst. Reply with JSON only using keys:
what_happened, why_important, beneficiaries (list), losers (list), expected_reaction,
time_horizon, confidence (0-1), catalysts (list), risks (list).
"""


class MockLLM:
    """Deterministic offline LLM used when USE_MOCK_LLM=true."""

    async def complete_json(self, system: str, user: str) -> dict:
        text = user.lower()
        beneficiaries: list[str] = []
        losers: list[str] = []
        if "nvidia" in text or "ai chip" in text:
            beneficiaries.append("NVDA")
            beneficiaries.append("semiconductor suppliers")
        if "oil" in text or "opec" in text:
            beneficiaries.append("XOM")
            losers.append("airlines")
        if "sanction" in text or "war" in text:
            beneficiaries.append("gold")
            beneficiaries.append("defense (LMT, RTX)")
            losers.append("EM equities")
        if "rate" in text or "federal reserve" in text:
            losers.append("growth stocks")
            beneficiaries.append("USD cash / short-duration bonds")
        if not beneficiaries:
            beneficiaries = ["unclear — needs more context"]
        if not losers:
            losers = ["unclear — needs more context"]

        bearish = any(w in text for w in ("plunge", "war", "sanction", "recession", "crash"))
        return {
            "what_happened": user[:280],
            "why_important": "Material for near-term price discovery and risk premia.",
            "beneficiaries": beneficiaries,
            "losers": losers,
            "expected_reaction": "risk-off" if bearish else "selective risk-on",
            "time_horizon": "1-10 trading days",
            "confidence": 0.55 if bearish else 0.6,
            "catalysts": re.findall(r"\b[A-Z]{2,5}\b", user)[:5] or ["headline flow"],
            "risks": ["headline reversal", "liquidity gaps", "model misspecification"],
        }


class OpenAILLM:
    """OpenAI chat completions adapter returning parsed JSON."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._api_key = api_key
        self._model = model

    async def complete_json(self, system: str, user: str) -> dict:
        import httpx

        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            res.raise_for_status()
            content = res.json()["choices"][0]["message"]["content"]
            return json.loads(content)


class LLMReasoningEngine:
    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    async def reason(self, event_text: str) -> LLMReasoningResult:
        raw = await self._llm.complete_json(SYSTEM_PROMPT, event_text)
        return LLMReasoningResult(
            what_happened=str(raw.get("what_happened", "")),
            why_important=str(raw.get("why_important", "")),
            beneficiaries=list(raw.get("beneficiaries", [])),
            losers=list(raw.get("losers", [])),
            expected_reaction=str(raw.get("expected_reaction", "")),
            time_horizon=str(raw.get("time_horizon", "")),
            confidence=float(raw.get("confidence", 0.5)),
            catalysts=list(raw.get("catalysts", [])),
            risks=list(raw.get("risks", [])),
            raw=raw,
        )
