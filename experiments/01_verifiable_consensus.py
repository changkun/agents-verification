"""Experiment 01 — Verifiable Consensus on a Real Codebase.

Sweeps (group-size, composition, question, trial) cells. For each cell, fans
out N agents in parallel against a clone of the pinned target repo, parses
their answers, and writes one record per cell to JSONL.

Records are flushed after every cell so a long run can be killed and resumed
with `--resume`. The analysis script in analysis/01_plot.py consumes the same
JSONL.

CLI:
  python experiments/01_verifiable_consensus.py --smoke           # quick check
  python experiments/01_verifiable_consensus.py                    # full run
  python experiments/01_verifiable_consensus.py --resume           # continue
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
CACHE_ROOT = REPO_ROOT / "_repo_cache"

sys.path.insert(0, str(REPO_ROOT))
from agents_byzantine_tolerance.agent import (  # noqa: E402
    Agent,
    AgentError,
    DEFAULT_CONFIGS,
)
from agents_byzantine_tolerance.consensus import parse_numeric  # noqa: E402
from agents_byzantine_tolerance.repo_cache import ensure_repo  # noqa: E402

# The system prompt enforces a parse-friendly output shape. Without this,
# agents commonly return "approximately 5" or "5 or 6" — both of which look
# like disagreement to the parser even when the underlying belief might match.
SYSTEM_PROMPT = """\
You are answering a verifiable question about a code repository. The repo
source is in your current working directory. Read files directly with your
tools — do not assume from memory.

Other independent agents are answering the same question in parallel. You are
NOT coordinating with them; just answer correctly.

Output rules (strict):
- Reply with a single non-negative integer on the FINAL line of your response.
- That final line must be only the integer. No commas, ranges, units, prefixes.
- If you are uncertain, give your best single integer estimate anyway.
"""

GROUP_SIZES_DEFAULT = [3, 5, 9]
COMPOSITIONS_DEFAULT = ["homogeneous-claude", "homogeneous-codex", "heterogeneous"]
TRIALS_DEFAULT = 5
DEFAULT_CONCURRENCY = 4
DEFAULT_TIMEOUT_S = 300


def build_agents(n: int, composition: str) -> list[Agent]:
    if composition == "homogeneous-claude":
        cfg = DEFAULT_CONFIGS["claude-haiku"]
        return [Agent(f"claude-{i}", cfg) for i in range(n)]
    if composition == "homogeneous-codex":
        cfg = DEFAULT_CONFIGS["codex-default"]
        return [Agent(f"codex-{i}", cfg) for i in range(n)]
    if composition == "heterogeneous":
        configs = [DEFAULT_CONFIGS["claude-haiku"], DEFAULT_CONFIGS["codex-default"]]
        return [Agent(f"agent-{i}-{configs[i % 2].kind.value}", configs[i % 2]) for i in range(n)]
    raise ValueError(f"unknown composition: {composition}")


_STRICT_INT = re.compile(r"^\s*(\d+)\s*[.)]?\s*$")


def parse_strict_int(text: str) -> int | None:
    """Return integer if the FINAL non-empty line is just one non-negative integer.

    The system prompt asks for exactly that shape; anything else (ranges,
    explanations, "I think", trailing words) is treated as a parse failure
    rather than silently extracted. That preserves disagreement signal —
    "5 or 6" should not silently count as the same answer as "6".
    """
    if not text:
        return None
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    m = _STRICT_INT.match(lines[-1])
    if not m:
        return None
    return int(m.group(1))


def _fallback_int(text: str) -> int | None:
    """Looser fallback used only for telemetry — not for consensus."""
    v = parse_numeric(text)
    if v is None:
        return None
    if v == int(v):
        return int(v)
    return None


async def run_cell(
    question: dict,
    n: int,
    composition: str,
    trial: int,
    seed_dir: Path,
    sem: asyncio.Semaphore,
    timeout_s: float,
) -> dict:
    agents = build_agents(n, composition)
    prompt = question["prompt"]

    async def one(agent: Agent) -> dict:
        async with sem:
            try:
                resp = await agent.query(
                    prompt,
                    system=SYSTEM_PROMPT,
                    seed_dir=seed_dir,
                    timeout=timeout_s,
                )
                parsed = parse_strict_int(resp.final_message)
                fallback = _fallback_int(resp.final_message)
                return {
                    "agent_id": agent.agent_id,
                    "kind": agent.config.kind.value,
                    "model": agent.config.model,
                    "raw_tail": resp.final_message[-1500:],
                    "parsed": parsed,
                    "fallback_parsed": fallback,
                    "rc": resp.returncode,
                    "error": None,
                }
            except AgentError as e:
                return {
                    "agent_id": agent.agent_id,
                    "kind": agent.config.kind.value,
                    "model": agent.config.model,
                    "raw_tail": "",
                    "parsed": None,
                    "fallback_parsed": None,
                    "rc": -1,
                    "error": str(e),
                }

    t0 = time.time()
    agent_results = await asyncio.gather(*(one(a) for a in agents))
    dt = time.time() - t0

    parsed = [r["parsed"] for r in agent_results]
    valid = [v for v in parsed if v is not None]
    counts = Counter(valid)
    if counts:
        majority_value, majority_count = counts.most_common(1)[0]
    else:
        majority_value, majority_count = None, 0

    n_distinct = len(counts)
    unanimous = bool(valid) and len(valid) == n and n_distinct == 1
    gt = question.get("ground_truth")
    any_correct = gt is not None and gt in valid

    return {
        "question_id": question["id"],
        "n": n,
        "composition": composition,
        "trial": trial,
        "ground_truth": gt,
        "duration_s": round(dt, 2),
        "agents": agent_results,
        "valid_count": len(valid),
        "unanimous": unanimous,
        "majority_value": majority_value,
        "majority_count": majority_count,
        "n_distinct": n_distinct,
        "any_correct": any_correct,
        "agreed_correct": (
            unanimous and gt is not None and majority_value == gt
        ),
    }


def already_done(path: Path) -> set[tuple]:
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        done.add((rec["question_id"], rec["n"], rec["composition"], rec["trial"]))
    return done


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--questions", default=str(REPO_ROOT / "experiments" / "questions.yaml"))
    ap.add_argument(
        "--output",
        default=None,
        help="output JSONL path (default: results/01_verifiable_consensus/<tag>.jsonl)",
    )
    ap.add_argument("--smoke", action="store_true", help="tiny config for end-to-end check")
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    ap.add_argument("--resume", action="store_true", help="skip cells already in output")
    ap.add_argument("--questions-only", help="comma-separated question IDs to run")
    ap.add_argument("--ns", help="comma-separated group sizes (default 3,5,9)")
    ap.add_argument("--compositions", help="comma-separated compositions")
    ap.add_argument("--trials", type=int, default=TRIALS_DEFAULT)
    args = ap.parse_args()

    bank_path = Path(args.questions)
    if not bank_path.exists():
        sys.stderr.write(
            f"questions file not found: {bank_path}\n"
            "Run: python experiments/01_compute_ground_truth.py\n"
        )
        return 1
    bank = yaml.safe_load(bank_path.read_text())

    target = bank["target_repo"]
    if not target.get("sha"):
        sys.stderr.write("target_repo.sha is null. Run 01_compute_ground_truth.py.\n")
        return 1

    print(f"[repo] ensuring cache pinned to {target['sha']}")
    seed_dir, actual_sha = ensure_repo(target["url"], target["sha"], CACHE_ROOT)
    if actual_sha != target["sha"]:
        sys.stderr.write(
            f"cache SHA mismatch: expected {target['sha']}, got {actual_sha}\n"
        )
        return 1

    if bank.get("agent_cwd_subpath"):
        seed_dir = seed_dir / bank["agent_cwd_subpath"]

    questions = [q for q in bank["questions"] if q.get("ground_truth") is not None]
    if args.questions_only:
        wanted = set(args.questions_only.split(","))
        questions = [q for q in questions if q["id"] in wanted]
    skipped = len(bank["questions"]) - len(questions)
    if skipped:
        print(f"[bank] skipping {skipped} questions without ground_truth")
    if not questions:
        sys.stderr.write("no questions to run\n")
        return 1

    if args.smoke:
        group_sizes = [3]
        compositions = ["homogeneous-claude"]
        trials = 1
        questions = questions[:2]
    else:
        group_sizes = (
            [int(x) for x in args.ns.split(",")] if args.ns else GROUP_SIZES_DEFAULT
        )
        compositions = (
            args.compositions.split(",") if args.compositions else COMPOSITIONS_DEFAULT
        )
        trials = args.trials

    if args.output is None:
        tag = "smoke" if args.smoke else "full"
        args.output = str(RESULTS_DIR / "01_verifiable_consensus" / f"{tag}.jsonl")
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = already_done(out_path) if args.resume else set()
    if not args.resume and out_path.exists():
        out_path.unlink()

    sem = asyncio.Semaphore(args.concurrency)
    cells = [
        (q, n, comp, t)
        for q in questions
        for n in group_sizes
        for comp in compositions
        for t in range(trials)
    ]
    total = len(cells)
    completed = 0

    print("=== Experiment 01: Verifiable Consensus ===")
    print(f"target:       {target['url']}@{target['sha'][:8]}")
    print(f"questions:    {len(questions)}  ({[q['id'] for q in questions]})")
    print(f"N:            {group_sizes}")
    print(f"compositions: {compositions}")
    print(f"trials/cell:  {trials}")
    print(f"total cells:  {total}  (resuming {len(done)})")
    print(f"concurrency:  {args.concurrency}")
    print(f"output:       {out_path}")
    print()

    with out_path.open("a") as fout:
        for q, n, comp, t in cells:
            key = (q["id"], n, comp, t)
            if key in done:
                completed += 1
                continue
            print(
                f"[{completed + 1}/{total}] {q['id']} N={n} {comp} trial={t}",
                flush=True,
            )
            try:
                rec = await run_cell(q, n, comp, t, seed_dir, sem, args.timeout)
            except Exception as exc:  # noqa: BLE001
                print(f"    !! cell failed: {exc!r}")
                completed += 1
                continue
            fout.write(json.dumps(rec) + "\n")
            fout.flush()
            mark = "✓" if rec["agreed_correct"] else ("·" if rec["any_correct"] else "✗")
            spread = "U" if rec["unanimous"] else f"D({rec['n_distinct']})"
            vals = [a["parsed"] for a in rec["agents"]]
            print(
                f"    {mark} {spread}  gt={rec['ground_truth']}  "
                f"vals={vals}  {rec['duration_s']}s"
            )
            completed += 1

    print(f"\nDone. {completed}/{total} cells.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
