from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


SUMMARY_COLUMNS = [
    "run",
    "file",
    "sample_count",
    "answerable_count",
    "source_hit_at_1",
    "source_hit_at_2",
    "source_hit_at_3",
    "source_hit_at_5",
    "mrr",
    "source_file_hit_rate",
    "content_type_hit_rate",
    "answer_pass_rate",
    "avg_elapsed_ms",
    "median_elapsed_ms",
    "avg_returned_docs",
]


def write_outputs(
    output_dir: Path,
    summary_rows: list[dict[str, Any]],
    sample_rows: list[dict[str, Any]],
    figures: list[Path],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "summary.csv", summary_rows, SUMMARY_COLUMNS)
    _write_csv(output_dir / "per_sample.csv", sample_rows, _sample_columns(sample_rows))
    _write_markdown(output_dir / "summary.md", summary_rows, sample_rows, figures)


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(
    path: Path,
    summary_rows: list[dict[str, Any]],
    sample_rows: list[dict[str, Any]],
    figures: list[Path],
) -> None:
    lines = [
        "# RAG Evaluation Analysis",
        "",
        f"Generated at `{datetime.now().isoformat(timespec='seconds')}`.",
        "",
        "## Summary",
        "",
        _markdown_table(
            summary_rows,
            [
                ("run", "Run"),
                ("source_hit_at_1", "Hit@1"),
                ("source_hit_at_3", "Hit@3"),
                ("source_hit_at_5", "Hit@5"),
                ("mrr", "MRR"),
                ("content_type_hit_rate", "Content Type"),
                ("answer_pass_rate", "Answer Pass"),
                ("avg_elapsed_ms", "Avg Latency"),
            ],
        ),
        "",
        "## Failure Breakdown",
        "",
        _failure_table(sample_rows),
        "",
        "## Figures",
        "",
    ]
    lines.extend(f"![{figure.stem}]({figure.name})" for figure in figures)
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `hit@k` is computed from the saved `retrieved_documents` order in each JSON report.",
            "- If a report saved fewer than `k` documents, this analysis cannot recover unseen candidates.",
            "- Existing reports do not store retrieval scores, so `MRR` is rank-based from document order only.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for _, label in columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(_display(row.get(key), key) for key, _ in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, divider, *body])


def _failure_table(sample_rows: list[dict[str, Any]]) -> str:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in sample_rows:
        counts[row["run"]][row["outcome"]] += 1
    outcomes = ["pass", "answer_or_metric_fail", "content_type_miss", "retrieval_miss", "refusal_fail", "error"]
    rows = [{"run": run, **{outcome: counter[outcome] for outcome in outcomes}} for run, counter in counts.items()]
    return _markdown_table(rows, [("run", "Run"), *[(item, item) for item in outcomes]])


def _sample_columns(rows: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "run",
        "id",
        "outcome",
        "first_source_rank",
        "hit_at_1",
        "hit_at_2",
        "hit_at_3",
        "hit_at_5",
        "source_file_hit",
        "content_type_hit",
        "answer_pass",
        "elapsed_ms",
        "difficulty",
        "answer_type",
        "tags",
        "expected_source_files",
        "top_source_files",
    ]
    rest = sorted({key for row in rows for key in row} - set(preferred))
    return preferred + rest


def _display(value: Any, key: str) -> str:
    if value is None:
        return ""
    if key.endswith("_ms") and isinstance(value, (int, float)):
        return f"{value / 1000:.1f}s"
    if isinstance(value, float):
        if key.endswith("_rate") or key.startswith("source_hit_at") or key == "mrr":
            return f"{value * 100:.1f}%"
        return f"{value:.2f}"
    return str(value)

