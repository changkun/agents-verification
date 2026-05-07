# Experiment 10 — Stochastic-System Soundness

## Thesis under test

Irving et al. (2018) proved debate soundness for *deterministic* AI systems.
Brown-Cohen, Irving, Piliouras (2023), *Scalable AI Safety via Doubly-Efficient
Debate* ([arXiv:2311.14125](https://arxiv.org/abs/2311.14125)), extended this
to *stochastic* systems — the formal license for applying debate to LLMs at
all. The spec 07 line implicitly assumes the extension carries over.
This spec tests it directly: does debate soundness hold across the
stochasticity range that real LLM deployments span, or does sampling noise
dominate the soundness signal at higher temperatures?

This is the smallest and sharpest spec in the new batch — a necessary-
condition check, not a search for a new architectural win. A null result
(soundness flat across T) licenses the rest of the spec 07 line. A positive
result (soundness drops above some T*) forces temperature pinning into every
debate deployment and means every prior 07 result needs a stochasticity
control.

## Architecture

Reuse 07a's debate runner unchanged. Sweep temperature on both players
independently. Hold rounds = 4, role assignment fixed, snippet bank from
07a. Trials per cell elevated to 20 for variance estimation.

## Independent variables

- **T_proposer** ∈ {0.0, 0.3, 0.7, 1.0}.
- **T_critic** ∈ {0.0, 0.3, 0.7, 1.0}.
- **Honesty**: {both honest, p-byzantine}.
- **Snippet bank**: 07a, restricted to 6 snippets to keep total
  invocations tractable: 4 × 4 × 2 × 6 × 20 = 3,840.

T_p and T_c are crossed (4×4 = 16 cells per honesty/snippet pair) so that
asymmetric effects ("hot critic, cold proposer") are visible.

## Comparison baseline

Matched-compute K-of-N voting at the same temperature settings. Voting
variance trivially scales with T (more sampling = more spread); the spec's
claim is that *debate soundness moves with T less than voting soundness
moves with T*.

## Metrics

1. **Soundness mean ± 95% CI vs (T_p, T_c)** — primary, plotted as a
   heatmap.
2. **Soundness variance across trials** — does T raise variance even when
   the mean stays flat?
3. **Critic-found-bug rate vs T_c** — does temperature help the critic?
4. **Byzantine-attack-success vs T_p** — does temperature help the
   proposer construct convincing lies?
5. **Soundness gap (debate − voting) vs T** — the comparative claim.

## Hypotheses

- **H1 (soundness mean flat).** Debate soundness mean is flat across T
  for both-honest cells; voting soundness is flat in mean but higher in
  variance.
- **H2 (hot Byzantine proposer evades).** Under p-byzantine, soundness
  drops at high T_p. A stochastic Byzantine proposer constructs more
  varied lies, harder for the critic to attack consistently.
- **H3 (critic temperature non-monotone).** Critic-found-bug rate peaks
  somewhere in (0.3, 0.7) — too cold is rigid, too hot is incoherent.
- **H4 (small interaction).** The T_p × T_c interaction is small —
  effects are roughly additive.

## Open questions / known risks

- **Temperature control via the CLI.** `claude -p` and `codex exec` may
  not expose temperature directly. Pilot first: confirm the knob exists
  and is plumbed through. If unavailable, this spec needs a workaround
  (header injection, CLI flag, or skipping the axis on one side).
- **Cell count.** 3,840 invocations is heavy. If pilot timing shows
  > 8 hours, drop to T ∈ {0.0, 0.7} on both sides (4 cells), losing the
  non-monotonicity probe in H3.
- **Variance entanglement under p-byzantine.** Sampling variance and
  Byzantine-injection variance both contribute. Report variance
  components separately (within-cell, across-snippet).
- **"Stochastic AI" in the paper vs. "LLM sampling" in practice.**
  Brown-Cohen et al. consider stochastic computation by the player; LLM
  temperature samples from a fixed distribution. These are not the same
  formal object. State this explicitly: a positive result here is
  empirical evidence consistent with the paper's extension, not a proof
  it transfers.

## Deliverable

- `experiments/10_stochastic.py` — runner.
- `results/10_stochastic/<tag>.jsonl`.
- `analysis/10_plot.py` — soundness heatmap over (T_p, T_c), variance
  decomposition, debate-vs-voting bars at each T.

## Exit criteria

- **H1 holds** → license to keep the spec 07 line as-is. Publish as
  supporting evidence; cited by every subsequent debate spec.
- **H1 fails** → temperature is a hidden IV in every other 07-line
  result. Rerun 07a at multiple T before concluding anything. This
  reshapes the project; it's the most important possible negative
  result in the new batch.

## Cross-references

- **vs 07**: 10 explicitly varies what 07a holds at T = 0 (default).
- **vs 02**: 10 measures stochastic Byzantine effect; 02 measures
  fixed-prompt Byzantine.
- **Prerequisite for 08, 09, 11**: if T matters for soundness, those
  specs need a temperature control. Run 10 first or in parallel; cite
  its result in the others' writeups.
