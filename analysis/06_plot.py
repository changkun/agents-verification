"""Analysis for Experiment 06 — Cascading Hallucination.

Per spec 06 §Metrics: stage error introduction/propagation/correction
rates, end-to-end correctness vs K, source-visibility delta.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "results" / "06_cascading" / "smoke.jsonl"


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def fmt(v, pct=False):
    if v is None:
        return "—"
    return f"{v * 100:.0f}%" if pct else f"{v:.2f}"


def write_summary(records: list[dict], out_path: Path) -> None:
    lines = ["# Experiment 06 — Cascading Hallucination", ""]
    lines.append(f"Total cells: {len(records)}")
    lines.append("")

    # End-to-end correctness by (condition, visibility).
    by_cv = defaultdict(list)
    for r in records:
        by_cv[(r["condition"], r["source_visibility"])].append(r)
    lines.append("## End-to-end correctness")
    lines.append("")
    lines.append("| condition | visibility | cells | end_to_end |")
    lines.append("|-----------|-----------|------:|-----------:|")
    for (c, v), cells in sorted(by_cv.items()):
        rate = sum(1 for r in cells if r["end_to_end_correct"]) / len(cells)
        lines.append(f"| {c} | {v} | {len(cells)} | {fmt(rate, pct=True)} |")
    lines.append("")
    lines.append(
        "*H2 prediction: every-stage visibility recovers ≥30pp over first-only "
        "in seeded conditions.*"
    )
    lines.append("")

    # Per-stage correctness.
    lines.append("## Per-stage correctness")
    lines.append("")
    lines.append("| stage | cells | correct |")
    lines.append("|-------|------:|--------:|")
    by_stage = defaultdict(list)
    for r in records:
        for s in r["stages"]:
            by_stage[s["stage_id"]].append(s["correct"])
    for sid in sorted(by_stage):
        cells = by_stage[sid]
        rate = sum(1 for c in cells if c) / len(cells)
        lines.append(f"| {sid} | {len(cells)} | {fmt(rate, pct=True)} |")
    lines.append("")

    # Propagation / correction (only meaningful with seeded runs).
    lines.append("## Propagation vs correction (seeded conditions only)")
    lines.append("")
    lines.append(
        "When the prior stage's input was the seeded (false) value, did this "
        "stage produce the correct output anyway (correction) or a wrong one "
        "(propagation)?"
    )
    lines.append("")
    lines.append("| visibility | seeded inputs | propagated wrong | corrected | correction_rate |")
    lines.append("|------------|--------------:|-----------------:|----------:|---------------:|")
    by_vis = defaultdict(list)
    for r in records:
        for s in r["stages"]:
            if s.get("input_was_seeded"):
                by_vis[r["source_visibility"]].append(s["correct"])
    for v in sorted(by_vis):
        cells = by_vis[v]
        cor = sum(1 for c in cells if c)
        lines.append(
            f"| {v} | {len(cells)} | {len(cells) - cor} | {cor} | "
            f"{fmt(cor / len(cells) if cells else None, pct=True)} |"
        )
    lines.append("")

    out_path.write_text("\n".join(lines))


def try_plots(records: list[dict], plot_dir: Path) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    plot_dir.mkdir(parents=True, exist_ok=True)

    # End-to-end correctness by condition and visibility.
    by_cv = defaultdict(list)
    for r in records:
        by_cv[(r["condition"], r["source_visibility"])].append(r)
    cells = sorted(by_cv)
    labels = [f"{c}\n{v}" for (c, v) in cells]
    ys = [
        sum(1 for r in by_cv[k] if r["end_to_end_correct"]) / len(by_cv[k])
        for k in cells
    ]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(labels, ys, color="#3a7ca5")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("End-to-end correctness")
    ax.set_title("Pipeline end-to-end correctness by condition × visibility")
    fig.tight_layout()
    fig.savefig(plot_dir / "end_to_end.png", dpi=140)
    plt.close(fig)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--summary", default=None)
    ap.add_argument("--plot-dir", default=None)
    ap.add_argument("--skip-plots", action="store_true")
    args = ap.parse_args()
    in_path = Path(args.input)
    if not in_path.exists():
        print(f"input not found: {in_path}")
        return 1
    records = load(in_path)
    if not records:
        print("no records")
        return 1
    summary_path = Path(args.summary) if args.summary else in_path.with_suffix(".summary.md")
    plot_dir = Path(args.plot_dir) if args.plot_dir else in_path.with_suffix(".plots")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    write_summary(records, summary_path)
    print(f"wrote {summary_path}")
    if not args.skip_plots and try_plots(records, plot_dir):
        print(f"wrote plots in {plot_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
