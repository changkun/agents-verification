# Experiment 09 — Debate Depth and Recursive Sub-Debate

## Thesis under test

The PSPACE intuition for debate (Irving et al. 2018) requires arbitrary
depth of cross-examination. Brown-Cohen, Irving, Piliouras (2023),
*Scalable AI Safety via Doubly-Efficient Debate*
([arXiv:2311.14125](https://arxiv.org/abs/2311.14125)), instantiate this via
recursive sub-debate: a leaf claim too complex for the judge spawns a nested
debate one level down, and the doubly-efficient property emerges from this
decomposition.

Spec 07 fixes the protocol at four flat rounds, which matches no theoretical
structure — it's a practical compromise between "enough rounds to find an
attack" and "few enough rounds to fit in context." This spec asks: does
soundness scale monotonically with round budget on the flat protocol, and
does recursive sub-debate beat flat extension at the same total compute?
The answer determines whether the productization path for spec 07 is "more
rounds" or "structured recursion."

## Architecture

**Flat-K only.** Alternating Proposer/Critic for K rounds, terminating
with a Critic stake. K ∈ {2, 4, 8, 12}. K=2 collapses to "propose +
attack" with no defense; report separately, do not pool with K≥4.

*Recursive sub-debate is no longer part of this spec.* Brown-Cohen,
Irving, Piliouras (2025) show that naive recursive debate is vulnerable
to obfuscation attacks; their Prover-Estimator protocol is the structurally
correct form of recursion. Spec 12 owns the recursive variant and tests it
head-to-head against this spec's flat-K results.

## Independent variables

- **Protocol**: {flat-2, flat-4, flat-8, flat-12}.
- **Honesty**: {both honest, p-byzantine, c-lazy}.
- **Snippet difficulty**: {easy, hard} split from 07a's bank — easy = bug
  surfaces in one input; hard = bug requires multi-step reasoning to
  trigger.
- **Roles**: claude-as-P / codex-as-C only (single role assignment to
  keep cell count tractable).

Trials per cell: 5. Total ≈ 4 × 3 × 2 × 5 ≈ 120 cells × snippets.

## Comparison baseline

flat-4 (= spec 07a). Plus matched-compute voting at total tokens used by
each protocol cell. Spec 12's Prover-Estimator result is the head-to-head
benchmark for recursion at matched compute (cross-spec comparison).

## Metrics

1. **Soundness vs round count** — does it monotone improve, plateau, or
   invert?
2. **Critic-found-bug rate vs round count** — does the critic find new
   bugs with more rounds, or repeat itself? Track *novel* attacks per
   round, not cumulative.
3. **Token cost per debate** — flat scales linearly with K.

Headline plot: **soundness vs round count K**, colored by honesty,
faceted by snippet difficulty, with matched-compute voting baseline as
a horizontal reference and spec 12's Prover-Estimator soundness as a
second reference line.

## Hypotheses

- **H1 (flat plateau).** Flat soundness rises from K=2 to K=4 then
  plateaus through K=12 — diminishing returns, because a bounded-
  rationality LLM can't usefully extend an attack indefinitely.
- **H2 (flat is bounded by single-attack ceiling).** Flat soundness at
  K=12 is below spec 12's Prover-Estimator result on the same snippets
  at matched compute. Flat extension cannot match decomposition; this
  is the negative result that motivates spec 12 existing at all.
- **H3 (critic vocabulary exhaustion).** Critic-output novelty (lexical
  overlap between rounds) approaches 1.0 by R6 — additional rounds
  recycle attacks rather than producing new ones. Mechanistic
  explanation for H1.

## Open questions / known risks

- **Round-count protocol shape change.** K=2 has no defense round, so
  attack is the whole game. Don't compare K=2 and K=4 soundness directly;
  call it out as a different protocol shape.
- **Critic vocabulary exhaustion.** "Flat plateaus" might be a prompt-
  engineering artifact — the critic exhausts its attack templates by R2.
  H3 measures this directly via lexical novelty.
- **Cross-spec compute matching.** Spec 12's Prover-Estimator runs at
  its own compute envelope; matching tokens for the head-to-head
  reference line requires careful accounting per-snippet, not a single
  protocol average.

## Deliverable

- `experiments/09_debate_depth.py` — runner for flat-K.
- `results/09_debate_depth/<tag>.jsonl`.
- `analysis/09_plot.py` — soundness vs round count, novelty-per-round
  overlay, cross-reference line for spec 12 Prover-Estimator at matched
  compute.

## Exit criteria

- **H1 holds, H2 holds** → flat depth saturates; Prover-Estimator
  (spec 12) is the only way to gain further soundness. Justifies the
  productization path going through 12, not 09.
- **H1 fails (no plateau, monotone improvement)** → more flat rounds
  do help. Re-evaluate before committing to recursion as the answer.
- **H3 holds** → mechanistic explanation for H1: critic prompt is the
  binding constraint, not protocol depth. Suggests prompt-engineering
  is higher leverage than protocol redesign for flat debate.

## Cross-references

- **vs 07**: 09 sweeps the round count 07 fixes.
- **vs 08**: 09 varies protocol depth at fixed compute; 08 varies
  compute at fixed protocol. Both probe the 2023 theorem from
  different sides.
- **vs 12**: 12 owns the recursive variant — Prover-Estimator. 09's
  flat-K result is the baseline 12 must beat to justify its complexity.
- **vs 11**: 11's strict-tuple format may interact with the leaf check
  the flat-K judge runs; run 11 first to pin the leaf schema.
