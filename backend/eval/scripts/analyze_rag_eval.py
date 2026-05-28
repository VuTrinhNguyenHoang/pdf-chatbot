#!/usr/bin/env python3
"""Analyze saved RAG eval reports and generate CSV/Markdown/SVG summaries."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from rag_eval_analysis.metrics import DEFAULT_K_VALUES, analyze_runs, load_runs
from rag_eval_analysis.svg import hit_at_k_chart, latency_chart, metrics_overview, outcome_heatmap
from rag_eval_analysis.writers import write_outputs

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUNS_DIR = ROOT / "backend" / "eval" / "runs"
DEFAULT_ARTIFACTS_DIR = ROOT / "backend" / "eval" / "artifacts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="*", type=Path, help="Specific rag_eval_*.json reports")
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--dataset", type=Path, help="Dataset JSONL used to enrich rows with tags")
    parser.add_argument("--latest", type=int, default=0, help="Use the latest N reports from --runs-dir")
    parser.add_argument("--k", type=int, nargs="+", default=list(DEFAULT_K_VALUES), help="k values for hit@k")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_paths = _report_paths(args.reports, args.runs_dir, args.latest)
    if not report_paths:
        print(f"No rag_eval_*.json reports found in {args.runs_dir}")
        return 1

    output_dir = args.output_dir or _default_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    k_values = tuple(sorted(set(args.k)))

    runs = load_runs(report_paths, dataset=args.dataset)
    summary_rows, sample_rows = analyze_runs(runs, k_values)

    figures = [
        output_dir / "metrics_overview.svg",
        output_dir / "hit_at_k.svg",
        output_dir / "latency.svg",
        output_dir / "sample_outcomes.svg",
    ]
    metrics_overview(figures[0], summary_rows)
    hit_at_k_chart(figures[1], summary_rows, k_values)
    latency_chart(figures[2], summary_rows)
    outcome_heatmap(figures[3], sample_rows)
    write_outputs(output_dir, summary_rows, sample_rows, figures)

    print(f"Analyzed {len(report_paths)} report(s)")
    print(f"Wrote {output_dir / 'summary.md'}")
    print(f"Wrote {output_dir / 'summary.csv'}")
    print(f"Wrote {output_dir / 'per_sample.csv'}")
    return 0


def _report_paths(reports: list[Path], runs_dir: Path, latest: int) -> list[Path]:
    if reports:
        return reports
    paths = sorted(runs_dir.glob("rag_eval_*.json"), key=lambda path: path.stat().st_mtime)
    if latest > 0:
        paths = paths[-latest:]
    return paths


def _default_output_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_ARTIFACTS_DIR / f"rag_eval_analysis_{stamp}"


if __name__ == "__main__":
    raise SystemExit(main())

