# Spec 08 — Debate Plugin for Claude Code

## What this spec is

**Tool spec, not experiment spec.** This productizes the architecture from spec 07 as a Claude Code plugin and a standalone CLI. Spec 07 measures whether debate works on coding tasks; spec 08 specifies a tool that bets it does, in a way that fails gracefully if 07's H6 (lazy critic collapses the architecture) bites.

## Goal

When Claude finishes a coding task, run a critic (Codex by default) that produces concrete adversarial comments on the diff. Claude either fixes or defends each comment. Up to N rounds of cross-examination. Unresolved leaves surface to the human at the end as a structured review. The human inspects only what wasn't resolved by debate, not the full output.

## Architecture

- **Proposer (P)** — the Claude Code session that just wrote code. Sees the original task and its own diff.
- **Critic(s) (C₁..Cₖ)** — k independent adversarial agents (Codex by default), each scoped to a different aspect (correctness, security, perf, …). Sees the diff + task context only.
- **Judge** — the human, but only at the end and only on unresolved leaves. Optional LLM-judge mode for triage.
- **Mediator** — a small orchestrator process that routes messages between P and the Cᵢ and tracks per-claim resolution state. This is the actual binary we ship.

Rounds:

1. **R0 — Trigger.** Claude finishes a coding task (Stop hook, or manual `/debate`).
2. **R1 — Attack.** Each Cᵢ produces a structured attack list against the diff. Each attack must name a concrete leaf: `{location, claim, expected violation, reproduction}`. Attacks lacking a reproduction are dropped at parse time, not by the proposer.
3. **R2 — Defense.** P responds to each attack with one of: `concede` (and apply fix), `rebut` (with specific counter-evidence), `push-back` (request clarification — only allowed once per attack).
4. **R3..R(max_turn) — Cross-examination.** Cs respond to defenses; P responds again; per-claim resolution state advances or stalls.
5. **Wrap-up.** Output unresolved-leaves review.

## Build options

### Option A — Pure Claude Code plugin (Stop hook does everything)

Hook script invokes Codex via shell, parses output, uses `claude --resume` (or session continuation) to feed attacks back into Claude.

- Pro: one artifact, zero-config if both CLIs are installed.
- Con: orchestration buried in a hook script; hard to reuse from CI; multi-critic gets ugly fast.
- Verdict: only viable if the plugin is small. With multi-critic + multi-turn it's wrong.

### Option B — External CLI orchestrator only

A standalone `debate` binary spawns proposer and critic CLIs, mediates rounds, prints the wrap-up.

```
debate --max-turn=10 --main claude --side codex --side-count=3 \
       --aspect correctness,security,perf
```

- Pro: composable; works in CI; trivially supports new critics (Gemini, local model); multi-critic is just more subprocess spawns.
- Con: not native to Claude Code; user must invoke manually.
- Verdict: this is the right primitive. Should exist regardless of whether a plugin exists.

### Option C — Hybrid: CLI orchestrator + thin Claude Code plugin (recommended)

Build B as the core. Ship a Claude Code plugin whose Stop hook (or `/debate` slash command) is a tiny shell wrapper that invokes B with the current session's diff and original task.

- Pro: orchestrator is reusable; plugin is ergonomic; critic logic lives in one place.
- Con: two artifacts.
- Verdict: **recommended.** Ship the CLI first; the plugin is glue on top.

### Option D — Slash command, no Stop hook

Same backend as C, but invocation is always `/debate`, never automatic.

- Pro: user controls when to pay the cost; never disrupts flow.
- Con: easy to forget; defeats automatic verification.
- Verdict: ship both modes. **Default to manual** (slash command); auto-Stop is opt-in.

## CLI surface

```
debate [--main claude] [--side codex] [--side-count 1]
       [--max-turn 6] [--aspect general]
       [--diff-from HEAD] [--diff-to .]
       [--task-context "<original task>"]
       [--judge none|llm|human]
       [--cost-cap 50000]
       [--output review.md] [--format markdown|json]
```

Notes:

- `--side-count` and `--aspect` interact: if `--aspect a,b,c` is given with `--side-count 3`, each critic gets one aspect. If counts mismatch, error.
- `--max-turn` counts P+C exchanges combined. 6 = 3 attack rounds + 3 defense rounds.
- `--task-context` is mandatory in CLI mode. The critic without task context produces irrelevant attacks ("why does this function exist?"). The plugin populates this from the Claude Code session automatically.
- `--cost-cap` is mandatory and aborts gracefully (surfaces partial review). Multi-critic multi-turn debates blow token budgets fast.
- Exit code 0 if zero unresolved leaves, 1 otherwise. Lets it gate CI.

## Plugin surface (Claude Code)

```
.claude/plugins/debate/
  hooks/Stop.sh         # invokes `debate` with session diff + task
  commands/debate.md    # /debate slash command, manual invocation
  config.json           # defaults
```

Default config: `/debate` enabled (manual), Stop hook **disabled**. User opts in with `"trigger": "stop"` in plugin config.

## Configuration

Project-level `.debate.toml` overrides plugin defaults:

```toml
max_turn = 6
side_count = 2
aspects = ["correctness", "security"]
cost_cap_tokens = 50000
trigger = "manual"           # "manual" | "stop"
allow_style_attacks = false  # default: critic must attack behavior, not style
```

## Termination conditions

The mediator terminates and writes the review when any of these fire:

1. **Steady state** — no new attacks two rounds running.
2. **Max turn** — hard cap reached.
3. **Cost cap** — token budget hit.
4. **Malformed output** — critic produces ill-formed attacks two rounds running (defensive: model is broken or prompt collapsed).
5. **User interrupt** — Ctrl-C.

The output header names which condition fired, so the human knows whether to trust "0 unresolved" (steady state) or treat it as truncation (max-turn / cost-cap).

## Output format

Markdown review:

```
# Debate review — terminated: steady-state | max-turn | cost-cap

## Resolved (12)
- [conceded] Off-by-one in pagination loop → fixed in src/api.py:42
- [rebutted] Race condition claim → critic withdrew after seeing lock at api.py:18

## Unresolved (3)  ← human reviews these
- [security/api.py:88] Critic: input not sanitized.
  Proposer: framework escapes.
  **Stake**: try input `';DROP TABLE--`. (decisive leaf, not yet executed)
- ...

## Stats
critic-found-real-issue rate: 7/15 attacks led to a fix
debate cost: 38k tokens, 6 turns, 2 critics
```

The unresolved section is the entire justification for the tool. If it's mostly noise, the tool fails. The "stats" block is for the user to spot-check whether the critic is actually working — if `critic-found-real-issue rate` is near 0 across many sessions, the user should disable the plugin.

## Risks

- **Lazy-critic risk (the binding one).** This is spec 07's H6. Codex may rubber-stamp. **Mitigation**: do not ship the plugin until spec 07a (bug detection, deterministic judge) returns critic-found-bug rate ≥ 60% on seeded bugs. If it's below 30%, this whole spec is dead on arrival.
- **Cost.** Multi-critic multi-turn debates 5–10x a coding session's token bill. Cost cap is mandatory; default it conservatively (50k tokens).
- **Flow disruption.** Auto-Stop on every completion is annoying for trivial edits. Default trigger is `manual`; auto is opt-in. Consider a `--changed-lines-min N` filter (only debate if diff is non-trivial).
- **Critic context starvation.** Critic only sees diff + task context, not the broader codebase. Produces false-positive attacks ("this function isn't called!" — yes it is, elsewhere). Mitigations: critic prompt requires concrete reproduction, and the proposer is allowed to rebut with `file:line` references the critic is forbidden from re-attacking.
- **Stylistic-gripe drift.** Critic attacks style not behavior. `allow_style_attacks = false` enforces it in the critic prompt; mediator drops style-shaped attacks at parse time.
- **Asymmetric truth.** Proposer has more context than critic; may over-defend when actually wrong. Mitigation: `--judge llm` mode triages unresolved leaves; default `none` just surfaces them and trusts the human.
- **Critic colludes with proposer.** If critic and proposer share a model family, they're more likely to agree on the same wrong answer. **Heterogeneity is structural here, not optional** — Claude proposer + Codex critic is the default for a reason. Don't ship a Claude-vs-Claude default.

## Out of scope

- Training a better critic. Use whatever Codex gives us; if it's bad, the tool fails (and that's the right outcome).
- Streaming TUI. v1 is batch.
- Persistent debate state across sessions. Each invocation is fresh against the current diff.
- Critic tool access beyond reading the diff and the task context. Deliberate — keeps the critic narrow and prevents critic-rabbit-holes.
- Auto-applying critic-suggested fixes. Concession-fixes are written by the proposer, not the critic. The critic never edits.

## Relationship to spec 07

Spec 07 is the *experiment* that validates whether debate works on coding tasks. Spec 08 is the *tool* that ships the architecture. **Spec 08 should not be built before spec 07a returns positive on H1 (debate beats voting at equal compute) and not-bitten on H6 (lazy critic).** Order of work:

1. Run 07a (bug detection, deterministic judge, 2-player honest debate) — measure critic-found-bug rate.
2. If ≥ 60%: build 08's CLI orchestrator (Option B).
3. If 07a also shows H1 holds: build 08's plugin layer (Option C).
4. If 07's H6 bites (lazy critic): re-prompt critic, re-measure; if still bad, abandon 08.

This ordering means 08 is gated on a real measurement, not a hope.
