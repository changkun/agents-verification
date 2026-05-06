"""Experiment 06 — Cascading Hallucination in Sequential Agent Chains.

For each pipeline × seed-condition × source-visibility × composition × trial:
runs K stages sequentially. Each stage k consumes stage k-1's output (or
the seed for that stage if injected). Records per-stage correctness against
the pipeline's ground truth, plus end-to-end correctness.

CLI:
  python experiments/06_cascading.py --smoke
  python experiments/06_cascading.py --conditions clean,seeded-subtle \\
      --visibilities first-only,every-stage --trials 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
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
You are one stage in a multi-agent pipeline. You receive structured input
and must produce structured output for the next stage. Follow the prompt
exactly and reply with the requested value on the final line of your
response — no prose on that final line.
"""


_NUMERIC_TAIL = re.compile(r"(-?\d+(?:\.\d+)?)\s*[.)]?\s*$")


def parse_int(text: str) -> int | None:
    if not text:
        return None
    last = [ln.strip() for ln in text.splitlines() if ln.strip()][-1:]
    if not last:
        return None
    m = _NUMERIC_TAIL.match(last[0])
    if not m:
        return None
    try:
        v = float(m.group(1))
        return int(v) if v == int(v) else None
    except ValueError:
        return None


def parse_float(text: str) -> float | None:
    if not text:
        return None
    last = [ln.strip() for ln in text.splitlines() if ln.strip()][-1:]
    if not last:
        return None
    m = _NUMERIC_TAIL.match(last[0])
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


PARSERS = {"int": parse_int, "float": parse_float}


def correct_for_stage(parsed, gt, parser_name: str, tol: float = 1e-6) -> bool:
    if parsed is None:
        return False
    if parser_name == "int":
        return parsed == gt
    return abs(parsed - gt) <= tol


def build_stage_agent(stage_idx: int, composition: str) -> Agent:
    if composition == "all-claude":
        cfg = DEFAULT_CONFIGS["claude-haiku"]
    elif composition == "all-codex":
        cfg = DEFAULT_CONFIGS["codex-default"]
    elif composition == "alternating":
        cfgs = [DEFAULT_CONFIGS["claude-haiku"], DEFAULT_CONFIGS["codex-default"]]
        cfg = cfgs[stage_idx % 2]
    else:
        raise ValueError(composition)
    return Agent(f"stage{stage_idx}-{cfg.kind.value}", cfg)


async def run_pipeline(
    pipeline: dict,
    condition: str,
    visibility: str,
    composition: str,
    trial: int,
    sem: asyncio.Semaphore,
    timeout_s: float,
) -> dict:
    stages = pipeline["stages"]
    source = pipeline["source"]
    seeds = pipeline.get("seeds", {})
    seed = None
    if condition.startswith("seeded-"):
        seed = seeds.get(condition.removeprefix("seeded-"))
        if seed is None:
            raise ValueError(f"unknown seed: {condition}")

    stage_records: list[dict] = []
    prior_output = ""
    t0 = time.time()
    for idx, stage in enumerate(stages):
        # Decide what `prior_output` the next stage should receive.
        # For the seeded condition at the relevant stage_index we substitute.
        if idx == 0 or seed is None or idx != seed["stage_index"] + 1:
            # Use what the previous stage actually produced.
            input_for_this_stage = prior_output
        else:
            # idx == seed["stage_index"] + 1 means we're the *next* stage
            # after the seeded one. Replace prior_output with the seed value.
            input_for_this_stage = seed["false_value"]

        source_block = (
            f"\nSOURCE:\n{source}" if visibility == "every-stage" else ""
        )

        prompt = stage["prompt"].format(
            source=source,
            prior_output=input_for_this_stage,
            source_block=source_block,
        )
        agent = build_stage_agent(idx, composition)

        async with sem:
            try:
                resp = await agent.query(
                    prompt, system=SYSTEM_PROMPT, timeout=timeout_s
                )
                parser = PARSERS[stage["parser"]]
                parsed = parser(resp.final_message)
                stage_record = {
                    "stage_index": idx,
                    "stage_id": stage["id"],
                    "agent_id": agent.agent_id,
                    "kind": agent.config.kind.value,
                    "model": agent.config.model,
                    "raw_tail": resp.final_message[-1500:],
                    "input_was_seeded": (
                        seed is not None and idx == seed["stage_index"] + 1
                    ),
                    "input_text": input_for_this_stage,
                    "parsed": parsed,
                    "ground_truth": stage["ground_truth"],
                    "correct": correct_for_stage(
                        parsed, stage["ground_truth"], stage["parser"]
                    ),
                    "rc": resp.returncode,
                    "error": None,
                }
            except AgentError as e:
                stage_record = {
                    "stage_index": idx,
                    "stage_id": stage["id"],
                    "agent_id": agent.agent_id,
                    "kind": agent.config.kind.value,
                    "model": agent.config.model,
                    "raw_tail": "",
                    "input_was_seeded": False,
                    "input_text": input_for_this_stage,
                    "parsed": None,
                    "ground_truth": stage["ground_truth"],
                    "correct": False,
                    "rc": -1,
                    "error": str(e),
                }
        stage_records.append(stage_record)
        # The next stage's prior_output is whatever this stage produced
        # (the raw final-line content, before parsing). If the seed comes
        # at the *current* stage_index, we'll override at injection time
        # (handled at the top of the loop).
        prior_output = (
            stage_record["raw_tail"].splitlines()[-1].strip()
            if stage_record["raw_tail"]
            else ""
        )

    dt = time.time() - t0
    return {
        "pipeline_id": pipeline["id"],
        "K": len(stages),
        "condition": condition,
        "source_visibility": visibility,
        "composition": composition,
        "trial": trial,
        "duration_s": round(dt, 2),
        "stages": stage_records,
        "end_to_end_correct": stage_records[-1]["correct"],
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
                rec["pipeline_id"],
                rec["condition"],
                rec["source_visibility"],
                rec["composition"],
                rec["trial"],
            )
        )
    return done


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pipelines", default=str(REPO_ROOT / "experiments" / "pipelines.yaml"))
    ap.add_argument("--output", default=None)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--conditions", help="default clean,seeded-subtle,seeded-obvious")
    ap.add_argument("--visibilities", help="default first-only,every-stage")
    ap.add_argument("--compositions", help="default all-claude,alternating")
    ap.add_argument("--trials", type=int, default=3)
    args = ap.parse_args()

    bank = yaml.safe_load(Path(args.pipelines).read_text())
    pipelines = bank["pipelines"]

    if args.smoke:
        conditions = ["clean", "seeded-subtle"]
        visibilities = ["first-only", "every-stage"]
        compositions = ["all-claude"]
        trials = 1
    else:
        conditions = (
            args.conditions.split(",")
            if args.conditions
            else ["clean", "seeded-subtle", "seeded-obvious"]
        )
        visibilities = (
            args.visibilities.split(",")
            if args.visibilities
            else ["first-only", "every-stage"]
        )
        compositions = (
            args.compositions.split(",")
            if args.compositions
            else ["all-claude", "alternating"]
        )
        trials = args.trials

    if args.output is None:
        tag = "smoke" if args.smoke else "full"
        args.output = str(RESULTS_DIR / "06_cascading" / f"{tag}.jsonl")
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = already_done(out_path) if args.resume else set()
    if not args.resume and out_path.exists():
        out_path.unlink()

    sem = asyncio.Semaphore(args.concurrency)
    cells = [
        (p, c, v, comp, t)
        for p in pipelines
        for c in conditions
        for v in visibilities
        for comp in compositions
        for t in range(trials)
    ]
    total = len(cells)
    completed = 0

    print("=== Experiment 06: Cascading Hallucination ===")
    print(f"pipelines:    {[p['id'] for p in pipelines]}")
    print(f"conditions:   {conditions}")
    print(f"visibilities: {visibilities}")
    print(f"compositions: {compositions}")
    print(f"trials:       {trials}")
    print(f"total cells:  {total}\n")

    with out_path.open("a") as fout:
        for p, c, v, comp, t in cells:
            key = (p["id"], c, v, comp, t)
            if key in done:
                completed += 1
                continue
            print(
                f"[{completed + 1}/{total}] {p['id']} {c} vis={v} {comp} trial={t}",
                flush=True,
            )
            try:
                rec = await run_pipeline(p, c, v, comp, t, sem, args.timeout)
            except Exception as exc:  # noqa: BLE001
                print(f"    !! {exc!r}")
                completed += 1
                continue
            fout.write(json.dumps(rec) + "\n")
            fout.flush()
            stages_str = " -> ".join(
                f"{s['stage_id']}:{s['parsed']}{'✓' if s['correct'] else '✗'}"
                for s in rec["stages"]
            )
            print(f"    {stages_str}  end={'✓' if rec['end_to_end_correct'] else '✗'}  {rec['duration_s']}s")
            completed += 1

    print(f"\nDone. {completed}/{total} cells.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
