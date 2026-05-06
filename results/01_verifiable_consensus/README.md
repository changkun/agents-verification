# Experiment 01 — Verifiable Consensus

Spec: [`specs/01-verifiable-consensus.md`](../../specs/01-verifiable-consensus.md)

## Run record

| Run    | Date       | Cells | Records | Cost | Reproducer |
|--------|------------|------:|--------:|------|------------|
| smoke  | 2026-05-06 | 2     | 6       | ~2 min wall | `python experiments/01_verifiable_consensus.py --smoke` |

The full-scale sweep prescribed by the spec (`N ∈ {3,5,9}` × 3 compositions × 12
questions × 5 trials = 540 cells, ~2,700 invocations) has not been run yet.
Run with `python experiments/01_verifiable_consensus.py` (no `--smoke`).

## Smoke configuration

- **Target**: `mvdan/sh@v3.10.0` (resolved SHA `392da98b03853d889822bc2f62d61f4f92f37fa4`)
- **Questions**: Q01 (exported funcs in `syntax/` taking `*Parser`; gt=0), Q02 (exported types in `syntax/printer.go`; gt=2)
- **N**: 3
- **Composition**: homogeneous-claude (claude-haiku-4-5)
- **Trials**: 1 per cell

Why so small: smoke exists to prove the pipeline (clone target → seed agent
workdirs → fan out → strict-parse → score against ground truth). It is
deliberately not enough data to test the spec's hypotheses.

## Outcome

Both cells produced **unanimous, correct** answers:

| Cell | gt | Agent values | Unanimous | Correct | Wall |
|------|---:|-------------|:--------:|:------:|-----:|
| Q01 N=3 homogeneous-claude | 0 | [0, 0, 0] | ✅ | ✅ | 110s |
| Q02 N=3 homogeneous-claude | 2 | [2, 2, 2] | ✅ | ✅ | 16s  |

H2 (the spec's central thesis — *unanimous → correct*) is consistent with this
sample, but a 2-cell sample is far too small to test it. Wait for the full run
before reading anything into these numbers.

The Q01 cell took ~7× the Q02 wall time despite the same N and prompt
shape — the agent appears to have spent more tool-use turns scanning
`syntax/` for *Parser before answering 0. That's the realistic agentic
failure surface the experiment was designed to expose, even though in this
case the answer was correct.

## Files

- [`smoke.jsonl`](smoke.jsonl) — raw per-cell records (one JSON object per line).
  Each record contains the full agent responses (truncated to last 1500 chars),
  parsed integer, ground truth, and computed metrics.
- [`smoke.summary.md`](smoke.summary.md) — markdown summary of all six metrics
  defined in the spec, broken down by N, composition, and question.
- [`smoke.plots/`](smoke.plots/) — headline plot + H1/H2/H3 per-hypothesis plots.
  With only 2 cells the plots are mostly empty; they exist to confirm the
  rendering pipeline.

## How to extend

1. Re-run `python experiments/01_compute_ground_truth.py` if the target ref or
   question bank changes.
2. Run `python experiments/01_verifiable_consensus.py` (no `--smoke`) for the
   prescribed full sweep. Use `--resume` to continue after interruption.
3. Run `python analysis/01_plot.py --input results/01_verifiable_consensus/full.jsonl`
   to regenerate analysis under the same naming convention.
