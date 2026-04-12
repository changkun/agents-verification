"""Smoke test: one Claude agent + one Codex agent answer a trivial question."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents_byzantine_tolerance.agent import Agent, DEFAULT_CONFIGS


async def main():
    claude = Agent("claude-1", DEFAULT_CONFIGS["claude-haiku"])
    codex = Agent("codex-1", DEFAULT_CONFIGS["codex-default"])

    prompt = "What is 2+2? Reply with only the number."

    print("Querying Claude...")
    r1 = await claude.query(prompt, timeout=120)
    print(f"  rc={r1.returncode}  final={r1.final_message!r}")
    if r1.returncode != 0:
        print(f"  stderr: {r1.stderr[:500]}")

    print("Querying Codex...")
    r2 = await codex.query(prompt, timeout=120)
    print(f"  rc={r2.returncode}  final={r2.final_message!r}")
    if r2.returncode != 0:
        print(f"  stderr: {r2.stderr[:500]}")


if __name__ == "__main__":
    asyncio.run(main())
