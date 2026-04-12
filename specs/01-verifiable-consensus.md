# Experiment 01 — Verifiable Consensus on a Real Codebase

## Thesis under test

From the blog post: "disagreement [is] the most informative signal rather than an obstacle to be averaged away."

If that thesis is right, we should see **agent disagreement correlate with incorrectness** — i.e. when N agents unanimously agree on an answer, they're more likely to be right than when they fracture into multiple groups.

This experiment separates two failure modes the blog emphasizes as distinct:
- **Liveness** — did the agents reach agreement at all?
- **Safety** — when they did agree, was the agreement correct?

Classical BFT gives deterministic safety guarantees. Stochastic agents don't, but we can measure the *empirical* relationship between agreement and correctness.

## Task design

Point N agents at a fixed, cloned open-source repository. Ask each one the same verifiable question in isolation. Questions are chosen so that:

1. **Ground truth exists** and can be computed mechanically by the experimenter.
2. **Trivial tools are insufficient** — the answer requires reading code, not just `wc -l` or `grep -c`. This forces the agent into its planning/reasoning loop, which is where realistic failure modes emerge.
3. **Numeric output** — a single integer or short string, so we can parse and cluster responses cleanly.

### Target repository

A single, pinned, public Go or Python repo of moderate size (~5–20k LOC). Candidate: a well-known library where we can hand-audit ground truth. Decision deferred to first run. Pin by commit SHA so ground truth is reproducible.

### Question bank (draft)

Each question has a ground-truth integer answer we compute separately and withhold from the agents.

| # | Question | Why it's interesting |
|---|----------|---------------------|
| Q1 | How many exported functions in package `X` take a `context.Context` as their first parameter? | Mechanical scan + interpretation of "exported" + "first parameter" |
| Q2 | How many distinct error types does package `Y` return from its public API? | Requires tracing return types through call chains |
| Q3 | How many public functions in file `Z.go` have cyclomatic complexity > 5? | Well-defined metric but tedious; invites shortcuts |
| Q4 | How many test files in the repo contain at least one test that calls `httptest.NewServer`? | Two-step: find test files, then scan their bodies |
| Q5 | How many `TODO`/`FIXME` comments mention a specific author by name? | Grep-able but agents may hallucinate the name spelling |

Target: 10–15 questions total. Each one is run across all trial conditions.

## Agent configuration

- **Homogeneous Claude**: N × `claude -p` with `claude-haiku-4-5` (fast, cheaper)
- **Homogeneous Codex**: N × `codex exec` with default model
- **Heterogeneous**: interleave Claude and Codex, N/2 each
- **Permissions**: `--permission-mode bypassPermissions` (Claude), `--sandbox read-only` (Codex). Agents can read the repo and run shell tools but not modify anything.
- **Isolation**: each agent runs in a fresh tempdir with a fresh clone of the target repo. No cross-agent visibility.

## Independent variables

- **Group size**: N ∈ {3, 5, 9}
- **Ensemble composition**: homogeneous-Claude, homogeneous-Codex, heterogeneous
- **Question**: the 10–15 questions above

Trials per (N, composition, question) cell: 5 initially. Total runs ≈ 9 × 15 × 5 = 675 agent invocations minimum. Adjust downward if cost is prohibitive.

## Metrics

For each (N, composition, question) cell:

1. **Unanimous agreement rate**: fraction of trials where all N agents returned the same value.
2. **Majority agreement rate**: fraction where ≥ ⌈N/2⌉ agents returned the same value.
3. **Correctness | unanimous**: P(answer correct | all agents agreed).
4. **Correctness | majority**: P(answer correct | majority agreed, use majority value).
5. **Correctness | full disagreement**: P(any agent correct | no two agents agreed).
6. **Disagreement-as-signal strength**: correlation between number of distinct values returned and distance from ground truth.

The headline plot: **correctness vs. agreement spread** across all runs. If the blog's thesis holds, unanimous answers should cluster near correct; fragmented answers should be all over the map.

## Hypotheses

- **H1 (liveness degrades with N)**: Unanimous agreement rate decreases as N grows, monotonically, across all question types. *(Replicates the Berdoz finding on a realistic task.)*
- **H2 (safety-via-agreement)**: Correctness given unanimous agreement > correctness given majority agreement > correctness given fragmented output. *(Validates the "disagreement is signal" thesis.)*
- **H3 (heterogeneity ≠ free lunch)**: Heterogeneous ensembles have *lower* unanimous rates than homogeneous ones (more model diversity → more disagreement) but *higher* correctness-given-unanimity (when they do agree, they've overcome independent failure modes).
- **H4 (question structure matters)**: Questions requiring interpretation (Q2, Q3) produce more disagreement than questions that are mostly mechanical (Q4, Q5). The experiment should expose which *types* of tasks are Byzantine-prone.

## Open questions / known risks

- **Cost**: Codex runs are slow (15–60s each). 675 runs × ~30s = ~5.5 hours wall-clock even with parallelism. Cap per-trial concurrency at ~4 to avoid rate limits.
- **Prompt-parsing brittleness**: agents may refuse to give a single integer and instead give ranges ("5 or 6 depending on how you count"). The parser must either accept this as "non-answer" (contributes to disagreement) or we must enforce output format more aggressively.
- **Ground-truth drift**: need to pin the repo SHA *and* manually audit each ground-truth answer before running. Experimenter error here contaminates the whole dataset.
- **Training-data contamination**: if the target repo is very popular, models may have memorized answers. Prefer a less-famous repo, or a specific commit not on HEAD.

## Deliverable

- `experiments/01_verifiable_consensus.py` — the runner.
- `experiments/questions.yaml` — the question bank with ground-truth answers (gitignored until we want to publish).
- `results/01_verifiable_consensus.json` — raw outcomes, one record per agent invocation.
- `analysis/01_plot.py` — generates the headline plots.

## Exit criteria

We stop and move to Experiment 02 when we have clear evidence for or against H2 (the "disagreement is signal" thesis). If H2 fails — if unanimous agents are just as wrong as fragmented ones — that's a more important finding than anything else here, and it reshapes the rest of the research.
