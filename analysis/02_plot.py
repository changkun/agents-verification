"""Analysis for Experiment 02 — Byzantine Injection.

Reads results/02_byzantine_injection/*.jsonl and emits:
  - <input>.summary.md            metrics 1–4 from the spec
  - <input>.plots/honest_curve.png honest-majority win rate vs f/N
  - <input>.plots/contamination.png Byzantine-contamination rate vs f/N
  - <input>.plots/efficacy.png    fraction of Byzantine agents that emitted the lie

Per spec 02 §Metrics:
  1. Honest-majority win rate
  2. Byzantine contamination rate
  3. No-consensus rate
  4. Threshold location (smallest f/N where honest-majority drops below 50%)
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "results" / "02_byzantine_injection" / "smoke.jsonl"


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def fmt(v: float | None, pct: bool = False) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.0f}%" if pct else f"{v:.2f}"


def cell_metrics(records: list[dict]) -> dict:
    total = len(records)
    if not total:
        return {
            "n": 0,
            "honest_win": None,
            "byz_win": None,
            "no_consensus": None,
            "byz_efficacy": None,
        }
    honest_win = sum(1 for r in records if r["honest_wins_majority"]) / total
    byz_win = sum(1 for r in records if r["byz_wins_majority"]) / total
    no_consensus = sum(1 for r in records if r["no_consensus"]) / total
    # Byzantine efficacy: fraction of injected agents that emitted the lie.
    total_byz = sum(r["byz_count"] for r in records)
    byz_efficacy = (
        sum(r["byz_emitted_false_count"] for r in records) / total_byz
        if total_byz
        else None
    )
    return {
        "n": total,
        "honest_win": honest_win,
        "byz_win": byz_win,
        "no_consensus": no_consensus,
        "byz_efficacy": byz_efficacy,
    }


def threshold_location(records: list[dict], floor: float = 0.5) -> float | None:
    """Smallest f/N where honest-majority win rate drops below floor."""
    by_ratio: dict[float, list[dict]] = defaultdict(list)
    for r in records:
        ratio = round(r["f"] / r["n"], 3)
        by_ratio[ratio].append(r)
    for ratio in sorted(by_ratio):
        m = cell_metrics(by_ratio[ratio])
        if m["honest_win"] is not None and m["honest_win"] < floor:
            return ratio
    return None


def write_summary(records: list[dict], out_path: Path) -> None:
    lines: list[str] = ["# Experiment 02 — Byzantine Injection", ""]
    lines.append(f"Total cells: {len(records)}")
    lines.append(f"Total invocations: {sum(len(r['agents']) for r in records)}")
    lines.append("")

    lines.append("## Overall")
    lines.append("")
    lines.append(_table([("all", cell_metrics(records))]))
    lines.append("")

    lines.append("## By f/N (the headline curve)")
    lines.append("")
    by_ratio = defaultdict(list)
    for r in records:
        by_ratio[(r["n"], r["f"])].append(r)
    rows = [
        (
            f"N={n} f={f} (f/N={f / n:.2f})",
            cell_metrics(by_ratio[(n, f)]),
        )
        for (n, f) in sorted(by_ratio)
    ]
    lines.append(_table(rows))
    lines.append("")
    thr = threshold_location(records)
    lines.append(
        f"Threshold (smallest f/N with honest-majority < 50%): **{thr}**"
        if thr is not None
        else "Threshold (smallest f/N with honest-majority < 50%): **not crossed**"
    )
    lines.append("")

    lines.append("## By strategy (H1 vs H2)")
    lines.append("")
    by_strat = defaultdict(list)
    for r in records:
        by_strat[r["strategy"]].append(r)
    rows = [(s, cell_metrics(by_strat[s])) for s in sorted(by_strat)]
    lines.append(_table(rows))
    lines.append("")
    lines.append("*H2 prediction: subtle misdirection contaminates at lower f/N than strong-lie.*")
    lines.append("")

    lines.append("## By composition (H3)")
    lines.append("")
    by_comp = defaultdict(list)
    for r in records:
        by_comp[r["composition"]].append(r)
    rows = [(c, cell_metrics(by_comp[c])) for c in sorted(by_comp)]
    lines.append(_table(rows))
    lines.append("")
    lines.append("*H3 prediction: heterogeneous tolerates higher f/N before contamination.*")
    lines.append("")

    lines.append("## Injection efficacy (sanity)")
    lines.append("")
    lines.append(
        "Fraction of designated Byzantine agents that actually emitted the "
        "injected false value (strong-lie strategy only). If this is near zero, "
        "the experiment isn't testing what it claims to test."
    )
    lines.append("")
    strong = [r for r in records if r["strategy"] == "strong"]
    lines.append(f"- Strong-lie efficacy: **{fmt(cell_metrics(strong)['byz_efficacy'], pct=True)}**")
    lines.append("")

    out_path.write_text("\n".join(lines))


def _table(rows: list[tuple[str, dict]]) -> str:
    header = "| group | cells | honest_wins | byz_wins | no_consensus | byz_efficacy |"
    sep = "|-------|------:|------------:|---------:|-------------:|-------------:|"
    out = [header, sep]
    for name, m in rows:
        out.append(
            f"| {name} | {m['n']} | {fmt(m['honest_win'], pct=True)} | "
            f"{fmt(m['byz_win'], pct=True)} | {fmt(m['no_consensus'], pct=True)} | "
            f"{fmt(m['byz_efficacy'], pct=True)} |"
        )
    return "\n".join(out)


def try_plots(records: list[dict], plot_dir: Path) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    plot_dir.mkdir(parents=True, exist_ok=True)

    by_ratio_strat: dict[tuple[float, str], list[dict]] = defaultdict(list)
    for r in records:
        ratio = round(r["f"] / r["n"], 3)
        by_ratio_strat[(ratio, r["strategy"])].append(r)
    ratios = sorted({k[0] for k in by_ratio_strat})
    strategies = sorted({k[1] for k in by_ratio_strat})

    fig, ax = plt.subplots(figsize=(6, 4))
    for s in strategies:
        ys = []
        for r in ratios:
            cell = by_ratio_strat.get((r, s), [])
            ys.append(cell_metrics(cell)["honest_win"] if cell else None)
        ax.plot(ratios, ys, marker="o", label=s)
    ax.axvline(1 / 3, color="gray", linestyle=":", label="classical f/N=1/3")
    ax.set_xlabel("Byzantine fraction f/N")
    ax.set_ylabel("Honest-majority win rate")
    ax.set_title("Honest-majority survival under Byzantine injection")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(plot_dir / "honest_curve.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    for s in strategies:
        ys = []
        for r in ratios:
            cell = by_ratio_strat.get((r, s), [])
            ys.append(cell_metrics(cell)["byz_win"] if cell else None)
        ax.plot(ratios, ys, marker="o", label=s)
    ax.set_xlabel("Byzantine fraction f/N")
    ax.set_ylabel("Byzantine value wins majority")
    ax.set_title("Byzantine contamination of consensus")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(plot_dir / "contamination.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    by_strat = defaultdict(list)
    for r in records:
        by_strat[r["strategy"]].append(r)
    labels = sorted(by_strat)
    vals = [cell_metrics(by_strat[s])["byz_efficacy"] or 0 for s in labels]
    ax.bar(labels, vals, color="#c0504d")
    ax.set_ylabel("Fraction of Byzantines emitting false value")
    ax.set_title("Injection efficacy (sanity)")
    ax.set_ylim(0, 1.05)
    fig.tight_layout()
    fig.savefig(plot_dir / "efficacy.png", dpi=140)
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
        print(f"no records in {in_path}")
        return 1

    summary_path = (
        Path(args.summary) if args.summary else in_path.with_suffix(".summary.md")
    )
    plot_dir = Path(args.plot_dir) if args.plot_dir else in_path.with_suffix(".plots")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    write_summary(records, summary_path)
    print(f"wrote {summary_path}")
    if args.skip_plots:
        return 0
    if try_plots(records, plot_dir):
        print(f"wrote plots in {plot_dir}")
    else:
        print("matplotlib not available")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
