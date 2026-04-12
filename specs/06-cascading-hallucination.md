# Experiment 06 — Cascading Hallucination in Sequential Agent Chains

## Thesis under test

From the blog: *"Hallucinations are seeded in a single agent and amplified by following ones due to over-reliance on textual flow. Vision tokens diminish in deeper agent turns, compounding accuracy loss."*

Experiments 01–05 study **parallel** consensus — N agents answer the same question independently. This experiment studies the **sequential** case: a pipeline of K agents where each consumes the previous agent's output. It's the other dominant multi-agent pattern, and the one where Byzantine errors *amplify* rather than average out.

Questions:
1. Do errors introduced early in a chain **propagate** through later stages (stay the same)?
2. Do they **amplify** (grow in magnitude)?
3. Do downstream agents ever **correct** upstream mistakes, or does the pipeline's trust in prior output kill recovery?
4. How does error growth scale with chain length K?

The blog implies amplification dominates. If that's right, any agent pipeline is a **fragility multiplier**, not a reliability multiplier — the opposite of classical BFT.

## Task design

Each trial runs a K-agent pipeline on a task with multiple stages. Example pipeline for a "research report" task:

1. **Agent 1 (summarizer)**: read a source document, extract 5 key facts.
2. **Agent 2 (analyst)**: given those 5 facts, identify implications.
3. **Agent 3 (writer)**: given implications, draft a conclusion paragraph.
4. **Agent 4 (editor)**: polish the conclusion.

Each stage has a well-defined input and output. Ground truth is held at each stage: we know what the correct facts, implications, and conclusion are.

### Task bank (draft)

- **Numeric pipeline**: parse a set of numbers → compute statistics → describe them. Errors are measurable in closed form.
- **Fact-extraction pipeline**: source doc → extract facts → answer a question requiring those facts.
- **Code-review pipeline**: read a diff → identify issues → prioritize → write a review comment.
- **Translation pipeline**: English → summary in English → translate summary to a target language → back-translate to English (round-trip check).

3–4 pipelines × multiple source documents = 20+ distinct trials.

## Seeded-error variants

For each pipeline, three conditions:

1. **Clean**: agents start with a correct input; measure how often errors *spontaneously arise* at each stage.
2. **Seeded-subtle**: Agent 1's output is replaced by the experimenter with a version containing one subtle factual error. Measure: does Agent 2/3/4 catch and correct it, or propagate/amplify?
3. **Seeded-obvious**: Agent 1's output has an obvious error (contradicts itself, flagrantly wrong number). Lower bar; agents should catch it.

The seeded variants are the core Byzantine test: one node emits bad data, and we measure how the rest of the chain handles it.

## Agent configuration

Each stage is a separate headless `claude -p` or `codex exec` invocation. Stages use different models within a pipeline to probe heterogeneity: e.g., Claude for stages 1 & 3, Codex for stages 2 & 4.

Agents see only:
- The system prompt describing their stage's role.
- The previous stage's output.
- **Optionally**: the original source document (independent variable).

That "optionally" matters — a pipeline that forces each agent to re-read the source can catch upstream errors; one that doesn't will propagate them. We test both.

## Independent variables

- **Chain length**: K ∈ {2, 4, 6}. Extend to 8 if runs complete cleanly.
- **Seed condition**: {clean, seeded-subtle, seeded-obvious}
- **Source visibility**: {first-stage only, every-stage}
- **Composition**: {all-Claude, all-Codex, alternating}
- **Pipeline**: 3–4 pipelines × multiple source docs

Trials per cell: 5. Cost is bounded by K × (cells), but K=6 means 6× the agent invocations per trial — budget ~3,000 invocations total.

## Metrics

Per-stage error metrics (computed from ground truth at each stage):

1. **Stage-k error introduction rate**: P(stage k output is wrong | stage k-1 output was right).
2. **Stage-k error propagation rate**: P(stage k output is wrong | stage k-1 output was wrong).
3. **Stage-k error correction rate**: P(stage k output is right | stage k-1 output was wrong). The blog predicts this is near zero without the source doc, much higher with it.
4. **Error magnitude**: for numeric pipelines, `|output_k − ground_truth_k|`. Does this grow with k?
5. **End-to-end correctness**: P(final output correct) as a function of K. The headline number.

## Hypotheses

- **H1 (propagation dominates correction)**: In seeded-subtle, first-stage-only visibility condition, P(propagate) >> P(correct) at every subsequent stage. Concretely: P(correct | upstream wrong) < 10%.
- **H2 (every-stage visibility enables recovery)**: Giving each stage access to the original source increases correction rate by ≥ 30 percentage points vs. first-stage-only. Direct architectural prescription: agent chains should re-ground against primary sources, not just downstream outputs.
- **H3 (end-to-end error is super-linear in K)**: Final correctness degrades faster than `(per-stage correctness)^K`, because errors compound rather than just accumulate. A weaker but still informative null: degradation is **at least** exponential in K.
- **H4 (obvious errors get caught even without re-grounding)**: Seeded-obvious errors are corrected at ≥ 80% rate even with first-stage-only visibility. Implies the propagation problem is specifically about plausible-looking errors.
- **H5 (heterogeneous chains resist propagation)**: Alternating Claude/Codex chains have lower propagation rates than homogeneous chains, because each stage's priors are uncorrelated with its predecessor's. Biggest expected effect of heterogeneity in the suite.

## Open questions / known risks

- **Ground truth at intermediate stages**: for some pipelines (e.g. "identify implications"), there's no single correct answer at stage 2, only at stage k. Restrict metrics to stages where ground truth is defined.
- **Prompt brittleness**: stages must produce output in a format the next stage can consume. Fragile prompts contaminate the signal. Budget time for pipeline-engineering in the pilot run before the full sweep.
- **Seeding looks like cheating**: replacing stage-1 output is an experimenter intervention, not a natural agent failure. The clean condition measures *natural* error rates; the seeded conditions measure *response to known errors*. Both are needed, and neither alone tells the full story.
- **"Correctness" at each stage is graded by an LLM judge** for non-numeric pipelines. That introduces its own Byzantine failure mode — use ≥ 3 independent judges, take majority, flag trials where judges disagree.
- **This is related to but distinct from RAG degradation**. Clarify in writeup: chained-agent compounding is a structural problem independent of retrieval quality.

## Deliverable

- `experiments/06_cascading.py` — the runner. Handles K stages with configurable visibility, seed, and composition.
- `experiments/pipelines/` — pipeline definitions (stage prompts, handoff format).
- `experiments/seeds/` — the subtle and obvious error injections per pipeline.
- `results/06_cascading.json`.
- `analysis/06_plot.py` — stage-by-stage error rate + end-to-end vs. K.

## Exit criteria

If H2 is confirmed (re-grounding against the source recovers ≥30pp of correctness), that is the single most actionable architectural recommendation from this entire research program — worth a standalone writeup. If H3 holds (super-linear error growth), the implication is that long agent chains are structurally unsafe regardless of per-stage quality, which is a strong negative result also worth publishing.
