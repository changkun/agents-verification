"""Consensus protocols for headless coding agents."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass

from .agent import Agent, AgentResponse


@dataclass
class ConsensusResult:
    """Result of a single consensus round."""

    responses: dict[str, AgentResponse]
    parsed_values: dict[str, float | None]
    agreed: bool = False
    agreed_value: float | None = None

    @property
    def valid_count(self) -> int:
        return sum(1 for v in self.parsed_values.values() if v is not None)

    @property
    def agreement_map(self) -> dict[float, list[str]]:
        """Partial agreement map: value -> agent_ids that proposed it."""
        groups: dict[float, list[str]] = {}
        for aid, val in self.parsed_values.items():
            if val is not None:
                groups.setdefault(val, []).append(aid)
        return groups


def parse_numeric(text: str) -> float | None:
    """Extract a numeric value from agent response text.

    Tries JSON, then 'answer is X' / 'final: X' patterns, then a trailing number.
    """
    text = text.strip()
    if not text:
        return None

    try:
        return float(json.loads(text))
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    patterns = [
        r"\b(?:final|answer|value|number|result|consensus)\s*(?:is|:|=)\s*(-?\d+(?:\.\d+)?)",
        r"(-?\d+(?:\.\d+)?)\s*$",
        r"^\s*(-?\d+(?:\.\d+)?)\s*$",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


async def scalar_consensus(
    agents: list[Agent],
    prompt: str,
    system: str | None = None,
    tolerance: float = 0.0,
    timeout: float = 180.0,
) -> ConsensusResult:
    """Single-shot scalar consensus: every agent answers in parallel, check agreement."""
    tasks = [agent.query(prompt, system=system, timeout=timeout) for agent in agents]
    responses_list = await asyncio.gather(*tasks, return_exceptions=True)

    responses: dict[str, AgentResponse] = {}
    parsed: dict[str, float | None] = {}

    for agent, resp in zip(agents, responses_list):
        if isinstance(resp, Exception):
            parsed[agent.agent_id] = None
            continue
        responses[agent.agent_id] = resp
        parsed[agent.agent_id] = parse_numeric(resp.final_message)

    result = ConsensusResult(responses=responses, parsed_values=parsed)

    valid_values = [v for v in parsed.values() if v is not None]
    if valid_values:
        ref = valid_values[0]
        if all(abs(v - ref) <= tolerance for v in valid_values):
            result.agreed = True
            result.agreed_value = ref

    return result
