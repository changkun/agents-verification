"""Experiment 03 — Bug-Detection Consensus.

For each snippet in the bank, fans out N agents to review the code+spec and
return `{has_bug: bool, lines: [int], kind: str}`. Aggregates per-snippet:
presence agreement, location agreement (±1 line tolerance), kind clustering.

CLI:
  python experiments/03_bug_detection.py --smoke
  python experiments/03_bug_detection.py --ns 3,5 --compositions homogeneous-claude
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"

sys.path.insert(0, str(REPO_ROOT))
from agents_byzantine_tolerance.agent import (  # noqa: E402
    Agent,
    AgentError,
    DEFAULT_CONFIGS,
)

SYSTEM_PROMPT = """\
You are reviewing a code snippet against a spec. You will be given:
  1. A short spec describing intended behaviour.
  2. A code snippet (with 1-indexed line numbers in your view of the file).

Decide whether the code has a bug *with respect to the spec*. A behaviour
that is internally consistent but unusual is NOT a bug if the spec accepts it.

Output rules (strict):
- Reply with a single JSON object on the FINAL line of your response.
- Schema: {"has_bug": bool, "lines": [int], "kind": "<short label>"}
- `lines` is a list of 1-indexed line numbers (in the snippet, NOT the spec)
  where the bug lives, or [] if no bug.
- `kind` is a short label like "off-by-one" or "race-condition", or ""
  if no bug.
- The JSON object must be the entire final line. No code fences, no commentary
  on that line.
"""

USER_TEMPLATE = """\
SPEC:
{spec}

CODE (1-indexed line numbers):
{numbered_code}

Question: does this code have a bug with respect to the spec? Reply per the
output rules.
"""


_JSON_LINE = re.compile(r"\{.*\}")


def _number_lines(code: str) -> str:
    return "\n".join(f"{i:>3}: {line}" for i, line in enumerate(code.splitlines(), 1))


def parse_review(text: str) -> dict | None:
    """Pick the JSON object from the final line of an agent response.

    Lenient: accepts a JSON object anywhere on the last few lines, validates
    the keys, casts shapes. Returns None on parse failure.
    """
    if not text:
        return None
    for line in reversed([ln for ln in text.splitlines() if ln.strip()][-5:]):
        m = _JSON_LINE.search(line)
        if not m:
            continue
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        out = {
            "has_bug": bool(obj.get("has_bug")),
            "lines": [
                int(x)
                for x in (obj.get("lines") or [])
                if isinstance(x, (int, float)) or (isinstance(x, str) and x.isdigit())
            ],
            "kind": str(obj.get("kind") or "").strip().lower(),
        }
        return out
    return None


def build_agents(n: int, composition: str) -> list[Agent]:
    if composition == "homogeneous-claude":
        cfg = DEFAULT_CONFIGS["claude-haiku"]
        return [Agent(f"claude-{i}", cfg) for i in range(n)]
    if composition == "homogeneous-codex":
        cfg = DEFAULT_CONFIGS["codex-default"]
        return [Agent(f"codex-{i}", cfg) for i in range(n)]
    if composition == "heterogeneous":
        configs = [DEFAULT_CONFIGS["claude-haiku"], DEFAULT_CONFIGS["codex-default"]]
        return [
            Agent(f"agent-{i}-{configs[i % 2].kind.value}", configs[i % 2])
            for i in range(n)
        ]
    raise ValueError(composition)


def _line_clusters(reviews: list[dict | None], tol: int = 1) -> list[set[int]]:
    """Cluster reviews by line set with ±tol tolerance.

    Two reviews share a cluster if their line sets contain at least one pair
    of integers within tol of each other. Cheap heuristic — good enough for
    counting agreement, not for nuanced reasoning.
    """
    sets = [set(r["lines"]) for r in reviews if r and r["has_bug"] and r["lines"]]
    n = len(sets)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if any(abs(a - b) <= tol for a in sets[i] for b in sets[j]):
                union(i, j)
    groups: dict[int, set[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), set()).add(i)
    return list(groups.values())


async def run_cell(
    snippet: dict,
    n: int,
    composition: str,
    trial: int,
    sem: asyncio.Semaphore,
    timeout_s: float,
) -> dict:
    agents = build_agents(n, composition)
    code = snippet["code"]
    user = USER_TEMPLATE.format(spec=snippet["spec"], numbered_code=_number_lines(code))

    async def one(agent: Agent) -> dict:
        async with sem:
            try:
                resp = await agent.query(
                    user, system=SYSTEM_PROMPT, timeout=timeout_s
                )
                review = parse_review(resp.final_message)
                return {
                    "agent_id": agent.agent_id,
                    "kind": agent.config.kind.value,
                    "model": agent.config.model,
                    "raw_tail": resp.final_message[-1500:],
                    "review": review,
                    "rc": resp.returncode,
                    "error": None,
                }
            except AgentError as e:
                return {
                    "agent_id": agent.agent_id,
                    "kind": agent.config.kind.value,
                    "model": agent.config.model,
                    "raw_tail": "",
                    "review": None,
                    "rc": -1,
                    "error": str(e),
                }

    t0 = time.time()
    agent_results = await asyncio.gather(*(one(a) for a in agents))
    dt = time.time() - t0

    reviews = [r["review"] for r in agent_results]
    parsed_reviews = [r for r in reviews if r is not None]
    presence = [r["has_bug"] for r in parsed_reviews]

    presence_agree = bool(parsed_reviews) and len(set(presence)) == 1
    presence_majority = (
        Counter(presence).most_common(1)[0][1] >= (n + 1) // 2 if presence else False
    )
    line_clusters = _line_clusters(parsed_reviews, tol=1)
    largest_cluster = max((len(c) for c in line_clusters), default=0)

    gt = snippet["ground_truth"]
    # Unanimous-yes correctness: all agents agree there's a bug AND there is one.
    unanimous_yes = (
        len(parsed_reviews) == n
        and all(p for p in presence)
        and len(line_clusters) == 1
    )
    unanimous_no = (
        len(parsed_reviews) == n
        and all(not p for p in presence)
    )
    correct_presence = (
        len(parsed_reviews) == n
        and Counter(presence).most_common(1)[0][0] == gt["has_bug"]
    )

    return {
        "snippet_id": snippet["id"],
        "category": snippet["category"],
        "n": n,
        "composition": composition,
        "trial": trial,
        "ground_truth": gt,
        "duration_s": round(dt, 2),
        "agents": agent_results,
        "valid_count": len(parsed_reviews),
        "presence_agree": presence_agree,
        "presence_majority": presence_majority,
        "line_cluster_count": len(line_clusters),
        "largest_line_cluster": largest_cluster,
        "unanimous_yes_aligned": unanimous_yes,
        "unanimous_no": unanimous_no,
        "correct_presence_majority": correct_presence,
    }


def already_done(path: Path) -> set[tuple]:
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        done.add((rec["snippet_id"], rec["n"], rec["composition"], rec["trial"]))
    return done


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snippets", default=str(REPO_ROOT / "experiments" / "snippets.yaml"))
    ap.add_argument("--output", default=None)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--ns", help="comma-separated group sizes (default 3,5,7)")
    ap.add_argument("--compositions", help="comma-separated compositions")
    ap.add_argument("--trials", type=int, default=3)
    args = ap.parse_args()

    bank = yaml.safe_load(Path(args.snippets).read_text())
    snippets = bank["snippets"]
    if args.smoke:
        ns = [3]
        compositions = ["homogeneous-claude"]
        trials = 1
    else:
        ns = [int(x) for x in args.ns.split(",")] if args.ns else [3, 5, 7]
        compositions = (
            args.compositions.split(",")
            if args.compositions
            else ["homogeneous-claude", "homogeneous-codex", "heterogeneous"]
        )
        trials = args.trials

    if args.output is None:
        tag = "smoke" if args.smoke else "full"
        args.output = str(RESULTS_DIR / "03_bug_detection" / f"{tag}.jsonl")
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = already_done(out_path) if args.resume else set()
    if not args.resume and out_path.exists():
        out_path.unlink()

    sem = asyncio.Semaphore(args.concurrency)
    cells = [
        (s, n, c, t)
        for s in snippets
        for n in ns
        for c in compositions
        for t in range(trials)
    ]
    total = len(cells)
    completed = 0

    print("=== Experiment 03: Bug-Detection Consensus ===")
    print(f"snippets:     {[s['id'] + ':' + s['category'] for s in snippets]}")
    print(f"N:            {ns}")
    print(f"compositions: {compositions}")
    print(f"trials:       {trials}")
    print(f"total cells:  {total}\n")

    with out_path.open("a") as fout:
        for s, n, comp, t in cells:
            key = (s["id"], n, comp, t)
            if key in done:
                completed += 1
                continue
            print(
                f"[{completed + 1}/{total}] {s['id']} ({s['category']}) "
                f"N={n} {comp} trial={t}",
                flush=True,
            )
            try:
                rec = await run_cell(s, n, comp, t, sem, args.timeout)
            except Exception as exc:  # noqa: BLE001
                print(f"    !! {exc!r}")
                completed += 1
                continue
            fout.write(json.dumps(rec) + "\n")
            fout.flush()
            mark = "✓" if rec["correct_presence_majority"] else "✗"
            agree = "U" if rec["presence_agree"] else f"D({rec['line_cluster_count']})"
            presents = [
                (r["review"]["has_bug"] if r["review"] else None)
                for r in rec["agents"]
            ]
            lines = [
                (r["review"]["lines"] if r["review"] else None) for r in rec["agents"]
            ]
            print(
                f"    {mark} {agree}  gt_has_bug={rec['ground_truth']['has_bug']}  "
                f"present={presents} lines={lines}  {rec['duration_s']}s"
            )
            completed += 1

    print(f"\nDone. {completed}/{total} cells.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
