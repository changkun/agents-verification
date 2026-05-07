# Experiment 13 — Debate Query Complexity Scaling

## Thesis under test

Brown-Cohen, Irving, Marshall, Newman, Piliouras, Szegedy (2026),
*Debate is Efficient with Your Time*
([arXiv:2602.08630](https://arxiv.org/abs/2602.08630)), introduce
**Debate Query Complexity (DQC)** — the minimum number of bits a judge
must inspect to verify a debate. Their headline result: PSPACE/poly is
exactly the class of functions decidable with O(log *n*) queries;
equivalently, for circuits of size *s*, DQC(*f*) ≤ log(*s*) + 3. This
sharpens spec 07's H5 ("cost-of-attention is real") and spec 11's
judge-read-tokens metric from "less is better" into a precise theoretical
reference: O(log *n*) is the floor; anything above linear means debate is
worse than reading the whole input.

Spec 11 measures the *soundness/cost Pareto at fixed task complexity*.
This spec measures the *scaling*: as snippet complexity *n* grows, does
empirical judge-read tokens grow as O(log *n*) — matching theory — or as
O(*n*^a) for some *a* > 0 — indicating LLM debate can't realize the
doubly-efficient property at scale? The regression slope of log(k*) vs.
log(*n*) is the headline number. A log slope is the strong positive
result; polynomial slope is the negative result that bounds the
deployment story.

## Architecture

Replace 07a's full-stake judge with a **budgeted judge** that sees only
the first *k* tokens of the staked leaf. Per (snippet, debate trial),
sweep *k* from a small floor (8 tokens) to the full stake length and
find:

> k* = min { k : judge-at-budget-k verdict equals judge-at-full-budget verdict }

k* is the empirical DQC for that (snippet, trial). The k-sweep operates
on cached transcripts — debates run once, then judges are re-evaluated
at every *k* — so the marginal cost is a judge call per *k*, not a
full debate.

## Independent variables

- **Snippet complexity *n***: small / medium / large by AST node count,
  with ~5 snippets per bucket. A new mini-bank designed to span ~3
  orders of magnitude in *n*. AST size is the primary measure; LOC and
  cyclomatic complexity reported as secondary.
- **Protocol**: {plain debate (07a), Prover-Estimator (spec 12)}. Tests
  whether the recursive protocol achieves better DQC scaling, the
  formal version of 12's compute-efficiency claim.
- **Honesty**: {both honest, p-byzantine}. The paper's theoretical
  bound is for adversarial play; honest play's DQC is a different
  question and worth measuring separately.
- **Judge mode**: {deterministic, llm-judge}. Deterministic isolates
  stake-format scaling; llm-judge is the deployment-relevant noisy
  case.

Trials per cell: 10 (need precision in slope estimation).

## Comparison baseline

The theoretical curve k* = α · log(*n*) + β (paper's upper bound). Plot
empirical k* against log(*n*). The headline scalar is the regression
slope of log(k*) vs. log(*n*):

- slope ≤ 0.3 → consistent with O(log *n*); LLM debate matches theory
  asymptotically.
- 0.3 < slope ≤ 0.8 → sub-linear but worse than theory; LLMs are
  sub-optimal players.
- slope > 0.8 → essentially proportional to input size; debate is no
  better than reading the snippet directly.

## Metrics

1. **Empirical DQC k*** per (snippet, trial) — primary, reported as
   scaling against *n*.
2. **Slope of log(k*) vs log(*n*)** — the headline scalar.
3. **Soundness at k*** — must equal full-budget soundness by
   construction; verify.
4. **Soundness-vs-k curve** below k* — how does soundness degrade as
   the judge sees less? Shape matters as much as the threshold.
5. **DQC ratio: Prover-Estimator vs. plain debate** — does the
   recursive protocol achieve a smaller k* slope under adversaries?

Headline plot: **log-log of k* vs. *n***, two lines (plain, PE) ×
two honesty conditions, with the theoretical α log *n* reference line
overlaid.

## Hypotheses

- **H1 (theoretical scaling holds for honest play).** Slope of
  log(k*) vs. log(*n*) is ≤ 0.3 under both-honest, for both protocols.
  LLM debate matches the doubly-efficient asymptotic when no one is
  lying.
- **H2 (Byzantine breaks plain-debate scaling).** Under p-byzantine,
  plain-debate slope rises to > 0.5. The theoretical O(log *n*) is for
  optimal-play; LLM adversaries push the empirical curve toward
  polynomial.
- **H3 (Prover-Estimator restores scaling).** Under p-byzantine,
  Prover-Estimator slope is ≤ 0.3 — restoring the asymptotic that the
  2025 paper's theorem promises against obfuscation. This is the
  formal version of spec 12's H2 ("PE resists obfuscation"): not just
  *whether* it resists, but *how its cost scales*.
- **H4 (lower bound respected).** Even on simplest snippets, k* ≥
  Ω(log *n*) — the paper's lower bound holds empirically. (Sanity
  check; failure means measurement error, not a counterexample to the
  theorem.)
- **H5 (judge mode shifts intercept, not slope).** LLM-judge has
  higher k* than deterministic judge at every *n*, but the slopes
  match. Judge noise is additive on the constant, not on the
  asymptotic.

## Open questions / known risks

- **Tokens ≠ bits.** The paper's DQC counts bits; we count tokens.
  Constants differ but asymptotic doesn't. The slope claim is robust
  to the constant; report this caveat explicitly.
- **AST node count is one complexity measure among several.** LOC,
  cyclomatic complexity, "distinct identifiers in scope," and
  estimated circuit-equivalent size are alternatives. Pilot all four
  on the snippet bank; pick the measure with the cleanest scaling on
  full-budget reference data and report sensitivity to the choice.
- **k-sweep is the expensive piece.** 3 buckets × 5 snippets × 2
  protocols × 2 honesty × 2 judges × 10 trials × ~12 *k* values per
  debate = ~14,400 judge invocations. The 1,200 full debates are the
  small piece; cache aggressively and let the k-sweep dominate
  *judge* compute.
- **Soundness preservation at *k* is judge-dependent.** A deterministic
  judge changes verdict in lockstep with whether the staked field is
  in the first *k* tokens — its k* is dominated by stake structure,
  not judge behavior. An LLM judge is noisier and more interesting.
  Both modes are reported; the deterministic slope is the cleaner
  test of stake-format scaling.
- **Snippet bank construction.** Spanning ~3 orders of magnitude in
  AST size while keeping all snippets bug-detection-amenable is a
  curation problem. Reuse 07a's bank where complexity allows; add new
  snippets at the high end.

## Deliverable

- `experiments/13_dqc_scaling.py` — runner with cached-transcript
  replay and budgeted-judge k-sweep.
- `experiments/snippets_complexity.yaml` — new bank with measured AST
  sizes (and LOC, cyclomatic) per snippet.
- `experiments/_budgeted_judge.py` — judge that takes
  `--max-stake-tokens k` and either truncates the stake (deterministic
  case) or shows only the first *k* tokens to the LLM judge.
- `results/13_dqc_scaling/<tag>.jsonl` — one record per (snippet,
  trial, *k*).
- `analysis/13_plot.py` — log-log of k* vs. *n* with theoretical
  reference; soundness-vs-*k* curves per complexity bucket;
  protocol-comparison bars.

## Exit criteria

- **H1 + H3 hold** → LLM debate matches theory asymptotically;
  Prover-Estimator restores honest-scaling under adversaries. Strong
  positive result; justifies the productized protocol's scalability
  claim.
- **H1 holds, H2 holds, H3 fails** → adversaries push debate off the
  doubly-efficient curve and Prover-Estimator doesn't restore it for
  LLMs. The paper's theorem holds; LLM instantiation doesn't reach
  it. Important negative result.
- **H1 fails** (slope > 0.5 even under honest) → LLM debate doesn't
  achieve the asymptotic at all. Re-evaluate the 07–12 productization
  story.
- **H4 fails** → measurement error; recheck token-counting before
  publishing anything else from this batch.

## Cross-references

- **vs 07**: 13 sharpens 07's H5 (cost-of-attention is real) into a
  quantitative scaling claim with a theoretical reference line.
- **vs 11**: 11 measures Pareto at fixed *n*; 13 measures scaling
  across *n*. They compose. Use 11's recommended leaf format
  (probably strict-tuple) as the leaf for 13's k-sweep.
- **vs 12**: 13 includes Prover-Estimator as a protocol IV. H3 is the
  formal scaling version of 12's H2 ("PE resists obfuscation") —
  whether PE not only wins, but wins *cheaply* at scale.
- **vs 08**: 08's compute-asymmetry result is on the prover/critic
  side; 13's DQC is on the judge side. Together they characterize
  total compute per role.
