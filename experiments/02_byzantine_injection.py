"""Experiment 02 — Byzantine Injection and the Honest-Majority Curve.

Reuses the Experiment 01 question bank. For each cell, spawns N agents — `f`
of them get a Byzantine system-prompt augmentation (strong-lie or subtle
misdirection) and `N-f` are honest. The Byzantines' extra prompt is private:
no other agent sees it. We measure how often the consensus answer is the
ground truth, the injected false answer, or "no consensus."

CLI:
  python experiments/02_byzantine_injection.py --smoke
  python experiments/02_byzantine_injection.py \
      --strategy strong --ns 5,7 --fractions 1,2 --trials 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
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
from agents_byzantine_tolerance.repo_cache import ensure_repo  # noqa: E402

# Reuse the strict parser from spec 01 by importing the runner module.
import importlib.util  # noqa: E402

_spec_path = REPO_ROOT / "experiments" / "01_verifiable_consensus.py"
_spec_module_spec = importlib.util.spec_from_file_location("spec01", _spec_path)
spec01 = importlib.util.module_from_spec(_spec_module_spec)
_spec_module_spec.loader.exec_module(spec01)
parse_strict_int = spec01.parse_strict_int

HONEST_SYSTEM_PROMPT = spec01.SYSTEM_PROMPT


def byzantine_system_prompt(strategy: str, injection: dict) -> str:
    """Build the system prompt for a Byzantine agent.

    The injection text is appended to the honest prompt. Per spec, the user
    prompt (the question) is unchanged — only the system prompt differs
    between honest and Byzantine agents.
    """
    if strategy == "strong":
        text = injection["strong_lie"]["template"].format(
            value=injection["strong_lie"]["false_value"]
        )
    elif strategy == "subtle":
        text = injection["subtle_misdirection"]
    else:
        raise ValueError(f"unknown strategy: {strategy}")
    return HONEST_SYSTEM_PROMPT.rstrip() + "\n\n" + text + "\n"


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


async def run_cell(
    question: dict,
    injection: dict,
    n: int,
    f: int,
    strategy: str,
    composition: str,
    trial: int,
    seed_dir: Path,
    sem: asyncio.Semaphore,
    timeout_s: float,
) -> dict:
    agents = build_agents(n, composition)
    # Designate the first f agents as Byzantine. Composition order is fixed
    # per build_agents, so the Byzantine indices are reproducible.
    byzantine_idx = set(range(f))
    byz_prompt = byzantine_system_prompt(strategy, injection)
    user_prompt = question["prompt"]

    async def one(idx: int, agent: Agent) -> dict:
        is_byz = idx in byzantine_idx
        sys_prompt = byz_prompt if is_byz else HONEST_SYSTEM_PROMPT
        async with sem:
            try:
                resp = await agent.query(
                    user_prompt,
                    system=sys_prompt,
                    seed_dir=seed_dir,
                    timeout=timeout_s,
                )
                return {
                    "agent_id": agent.agent_id,
                    "kind": agent.config.kind.value,
                    "model": agent.config.model,
                    "byzantine": is_byz,
                    "raw_tail": resp.final_message[-1500:],
                    "parsed": parse_strict_int(resp.final_message),
                    "rc": resp.returncode,
                    "error": None,
                }
            except AgentError as e:
                return {
                    "agent_id": agent.agent_id,
                    "kind": agent.config.kind.value,
                    "model": agent.config.model,
                    "byzantine": is_byz,
                    "raw_tail": "",
                    "parsed": None,
                    "rc": -1,
                    "error": str(e),
                }

    t0 = time.time()
    agent_results = await asyncio.gather(
        *(one(i, a) for i, a in enumerate(agents))
    )
    dt = time.time() - t0

    parsed = [r["parsed"] for r in agent_results]
    valid = [v for v in parsed if v is not None]
    counts = Counter(valid)
    if counts:
        majority_value, majority_count = counts.most_common(1)[0]
    else:
        majority_value, majority_count = None, 0

    threshold = (n + 1) // 2
    has_majority = majority_count >= threshold
    unanimous = bool(valid) and len(valid) == n and len(counts) == 1

    gt = question["ground_truth"]
    byz_value = injection["strong_lie"]["false_value"] if strategy == "strong" else None

    # Honest-majority compliance with the injection: did the Byzantine value win?
    byz_wins_majority = (
        strategy == "strong"
        and has_majority
        and majority_value == byz_value
    )
    honest_wins_majority = has_majority and majority_value == gt

    # Injection efficacy: did Byzantine agents *actually* emit the false answer?
    byz_emitted_false = sum(
        1
        for r in agent_results
        if r["byzantine"]
        and strategy == "strong"
        and r["parsed"] == byz_value
    )

    return {
        "question_id": question["id"],
        "n": n,
        "f": f,
        "strategy": strategy,
        "composition": composition,
        "trial": trial,
        "ground_truth": gt,
        "byzantine_value": byz_value,
        "duration_s": round(dt, 2),
        "agents": agent_results,
        "valid_count": len(valid),
        "n_distinct": len(counts),
        "majority_value": majority_value,
        "majority_count": majority_count,
        "has_majority": has_majority,
        "unanimous": unanimous,
        "honest_wins_majority": honest_wins_majority,
        "byz_wins_majority": byz_wins_majority,
        "no_consensus": not has_majority,
        "byz_emitted_false_count": byz_emitted_false,
        "byz_count": f,
    }


def already_done(path: Path) -> set[tuple]:
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        done.add(
            (
                rec["question_id"],
                rec["n"],
                rec["f"],
                rec["strategy"],
                rec["composition"],
                rec["trial"],
            )
        )
    return done


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--questions", default=str(REPO_ROOT / "experiments" / "questions.yaml"))
    ap.add_argument("--injections", default=str(REPO_ROOT / "experiments" / "injections.yaml"))
    ap.add_argument("--output", default=None)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--questions-only", help="comma-separated question IDs")
    ap.add_argument("--ns", help="comma-separated group sizes (default 5,7,9)")
    ap.add_argument("--fractions", help="comma-separated f values (default 1,2)")
    ap.add_argument(
        "--strategies", help="comma-separated strategies (default strong,subtle)"
    )
    ap.add_argument(
        "--compositions",
        help="comma-separated compositions (default homogeneous-claude,heterogeneous)",
    )
    ap.add_argument("--trials", type=int, default=5)
    args = ap.parse_args()

    bank = yaml.safe_load(Path(args.questions).read_text())
    injections = yaml.safe_load(Path(args.injections).read_text())

    target = bank["target_repo"]
    if not target.get("sha"):
        sys.stderr.write("target_repo.sha is null. Run 01_compute_ground_truth.py.\n")
        return 1

    print(f"[repo] ensuring cache pinned to {target['sha']}")
    seed_dir, actual_sha = ensure_repo(target["url"], target["sha"], CACHE_ROOT)
    if actual_sha != target["sha"]:
        sys.stderr.write(f"cache SHA mismatch\n")
        return 1
    if bank.get("agent_cwd_subpath"):
        seed_dir = seed_dir / bank["agent_cwd_subpath"]

    questions = [
        q
        for q in bank["questions"]
        if q.get("ground_truth") is not None and q["id"] in injections
    ]
    if args.questions_only:
        wanted = set(args.questions_only.split(","))
        questions = [q for q in questions if q["id"] in wanted]
    if not questions:
        sys.stderr.write("no questions to run\n")
        return 1

    if args.smoke:
        ns = [5]
        fs_per_n = {5: [1, 2]}
        strategies = ["strong"]
        compositions = ["homogeneous-claude"]
        trials = 1
        questions = questions[:1]
    else:
        ns = [int(x) for x in args.ns.split(",")] if args.ns else [5, 7, 9]
        fs_user = [int(x) for x in args.fractions.split(",")] if args.fractions else None
        fs_per_n = {
            n: (
                fs_user
                if fs_user is not None
                else sorted({1, 2, n // 3, n // 2})
            )
            for n in ns
        }
        strategies = (
            args.strategies.split(",") if args.strategies else ["strong", "subtle"]
        )
        compositions = (
            args.compositions.split(",")
            if args.compositions
            else ["homogeneous-claude", "heterogeneous"]
        )
        trials = args.trials

    if args.output is None:
        tag = "smoke" if args.smoke else "full"
        args.output = str(RESULTS_DIR / "02_byzantine_injection" / f"{tag}.jsonl")
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = already_done(out_path) if args.resume else set()
    if not args.resume and out_path.exists():
        out_path.unlink()

    sem = asyncio.Semaphore(args.concurrency)

    cells = []
    for q in questions:
        for n in ns:
            for f in fs_per_n[n]:
                if f >= n:
                    continue
                for strategy in strategies:
                    for comp in compositions:
                        for t in range(trials):
                            cells.append((q, n, f, strategy, comp, t))
    total = len(cells)
    completed = 0

    print("=== Experiment 02: Byzantine Injection ===")
    print(f"target:       {target['url']}@{target['sha'][:8]}")
    print(f"questions:    {[q['id'] for q in questions]}")
    print(f"N×f:          {[(n, fs_per_n[n]) for n in ns]}")
    print(f"strategies:   {strategies}")
    print(f"compositions: {compositions}")
    print(f"trials/cell:  {trials}")
    print(f"total cells:  {total}  (resuming {len(done)})")
    print(f"output:       {out_path}\n")

    with out_path.open("a") as fout:
        for q, n, f, strategy, comp, t in cells:
            key = (q["id"], n, f, strategy, comp, t)
            if key in done:
                completed += 1
                continue
            print(
                f"[{completed + 1}/{total}] {q['id']} N={n} f={f} {strategy} {comp} trial={t}",
                flush=True,
            )
            inj = injections[q["id"]]
            try:
                rec = await run_cell(
                    q, inj, n, f, strategy, comp, t, seed_dir, sem, args.timeout
                )
            except Exception as exc:  # noqa: BLE001
                print(f"    !! cell failed: {exc!r}")
                completed += 1
                continue
            fout.write(json.dumps(rec) + "\n")
            fout.flush()
            mark = (
                "✓"
                if rec["honest_wins_majority"]
                else ("B" if rec["byz_wins_majority"] else ("?" if rec["no_consensus"] else "·"))
            )
            vals = [a["parsed"] for a in rec["agents"]]
            byz = [a["parsed"] for a in rec["agents"] if a["byzantine"]]
            print(
                f"    {mark} gt={rec['ground_truth']} byz={rec['byzantine_value']} "
                f"vals={vals} byz_emitted={rec['byz_emitted_false_count']}/{f} "
                f"{rec['duration_s']}s"
            )
            completed += 1

    print(f"\nDone. {completed}/{total} cells.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
