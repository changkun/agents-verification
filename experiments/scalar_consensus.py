"""Experiment: Scalar consensus across heterogeneous Claude/Codex agents.

The Byzantine setup: spawn N coding agents (mix of `claude -p` and `codex exec`
in headless mode), give them a task that requires agreement on a single number,
and measure (a) consensus rate and (b) the partial agreement map across trials.

This is adversarial in the sense that we use *full coding agents* (with planning
loops, tool access, the works) — not raw model calls — so all the realistic
failure modes of agentic systems show up.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents_byzantine_tolerance.agent import Agent, DEFAULT_CONFIGS
from agents_byzantine_tolerance.consensus import scalar_consensus

SYSTEM_PROMPT = (
    "You are participating in a multi-agent consensus protocol. "
    "Other independent agents are answering the same question in parallel. "
    "You must converge on a single integer between 1 and 100. "
    "Reply with ONLY the integer on the final line of your response. No extra text."
)

TASK_PROMPT = (
    "Pick an integer between 1 and 100 that other independent agents are most "
    "likely to also pick. Reply with only the integer."
)

GROUP_SIZES = [3, 6, 9]
TRIALS_PER_SIZE = 5


def make_homogeneous_claude(n: int) -> list[Agent]:
    cfg = DEFAULT_CONFIGS["claude-haiku"]
    return [Agent(f"claude-{i}", cfg) for i in range(n)]


def make_heterogeneous(n: int) -> list[Agent]:
    """Alternate Claude and Codex agents."""
    pool = [DEFAULT_CONFIGS["claude-haiku"], DEFAULT_CONFIGS["codex-default"]]
    return [Agent(f"agent-{i}-{pool[i % 2].kind.value}", pool[i % 2]) for i in range(n)]


async def run(group_sizes, trials, factory, label):
    out = {}
    for n in group_sizes:
        print(f"\n--- {label} | N={n} | {trials} trials ---")
        outcomes = []
        for t in range(trials):
            agents = factory(n)
            try:
                result = await scalar_consensus(
                    agents, TASK_PROMPT, system=SYSTEM_PROMPT, tolerance=0.0
                )
            except Exception as e:
                print(f"  trial {t}: ERROR {e}")
                continue

            outcomes.append({
                "trial": t,
                "agreed": result.agreed,
                "agreed_value": result.agreed_value,
                "valid_count": result.valid_count,
                "total": n,
                "agreement_map": {str(k): v for k, v in result.agreement_map.items()},
                "raw": {aid: r.final_message for aid, r in result.responses.items()},
            })

            status = "AGREE" if result.agreed else "DIVERGE"
            print(f"  trial {t}: {status} | {result.valid_count}/{n} valid | {len(result.agreement_map)} groups")

        agreed = sum(1 for o in outcomes if o["agreed"])
        out[n] = {
            "n_agents": n,
            "trials": len(outcomes),
            "consensus_rate": agreed / len(outcomes) if outcomes else 0,
            "outcomes": outcomes,
        }
        print(f"  consensus rate: {agreed}/{len(outcomes)}")
    return out


async def main():
    print("=== Scalar Consensus Experiment ===")
    print("Backend: claude -p + codex exec (headless mode)\n")

    homo = await run(GROUP_SIZES, TRIALS_PER_SIZE, make_homogeneous_claude, "homogeneous-claude")
    print("\n")
    hetero = await run(GROUP_SIZES, TRIALS_PER_SIZE, make_heterogeneous, "heterogeneous-claude+codex")

    out_dir = Path(__file__).parent.parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "scalar_consensus.json"
    out_path.write_text(json.dumps({
        "homogeneous_claude": {str(k): v for k, v in homo.items()},
        "heterogeneous": {str(k): v for k, v in hetero.items()},
    }, indent=2))
    print(f"\nResults: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
