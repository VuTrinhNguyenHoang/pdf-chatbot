from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_K_VALUES = (1, 2, 3, 5)


@dataclass(frozen=True)
class RunBundle:
    label: str
    path: Path
    report: dict[str, Any]
    dataset_by_id: dict[str, dict[str, Any]]


def load_dataset(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows[row["id"]] = row
    return rows


def load_runs(paths: list[Path], dataset: Path | None = None) -> list[RunBundle]:
    used_labels: set[str] = set()
    runs = []
    for path in sorted(paths):
        report = json.loads(path.read_text(encoding="utf-8"))
        dataset_path = dataset or _dataset_path(report)
        runs.append(
            RunBundle(
                label=_label_for(path, report, used_labels),
                path=path,
                report=report,
                dataset_by_id=load_dataset(dataset_path),
            )
        )
    return runs


def analyze_runs(
    runs: list[RunBundle],
    k_values: tuple[int, ...] = DEFAULT_K_VALUES,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summary_rows = [summarize_run(run, k_values) for run in runs]
    sample_rows = [row for run in runs for row in sample_rows_for_run(run, k_values)]
    return summary_rows, sample_rows


def summarize_run(run: RunBundle, k_values: tuple[int, ...]) -> dict[str, Any]:
    results = run.report.get("results") or []
    answerable = [item for item in results if item.get("answerable", True)]
    source_scored = [item for item in answerable if expected_files(item)]
    ranks = [first_source_rank(item) for item in source_scored]
    elapsed = [item["elapsed_ms"] for item in results if isinstance(item.get("elapsed_ms"), int)]
    docs_count = [len(item.get("retrieved_documents") or []) for item in results]

    row: dict[str, Any] = {
        "run": run.label,
        "file": run.path.name,
        "sample_count": len(results),
        "answerable_count": len(answerable),
        "source_file_hit_rate": _rate(item.get("source_file_hit") for item in source_scored),
        "content_type_hit_rate": _rate(
            item.get("content_type_hit")
            for item in answerable
            if item.get("content_type_hit") is not None
        ),
        "answer_pass_rate": _rate(
            item.get("answer_pass") for item in results if item.get("answer_pass") is not None
        ),
        "mrr": _mean((1 / rank) if rank else 0 for rank in ranks),
        "mean_first_source_rank": _mean(rank for rank in ranks if rank),
        "avg_elapsed_ms": _mean(elapsed),
        "median_elapsed_ms": statistics.median(elapsed) if elapsed else None,
        "avg_returned_docs": _mean(docs_count),
    }
    for k in k_values:
        row[f"source_hit_at_{k}"] = _rate((rank is not None and rank <= k) for rank in ranks)
        row[f"source_coverage_at_{k}"] = _mean(source_coverage_at_k(item, k) for item in source_scored)
    return _rounded(row)


def sample_rows_for_run(run: RunBundle, k_values: tuple[int, ...]) -> list[dict[str, Any]]:
    rows = []
    for item in run.report.get("results") or []:
        sample = run.dataset_by_id.get(item.get("id"), {})
        rank = first_source_rank(item)
        row: dict[str, Any] = {
            "run": run.label,
            "id": item.get("id"),
            "answerable": item.get("answerable", True),
            "difficulty": sample.get("difficulty", ""),
            "answer_type": sample.get("answer_type", ""),
            "tags": ",".join(sample.get("tags") or []),
            "outcome": outcome_for(item),
            "first_source_rank": rank or "",
            "source_file_hit": item.get("source_file_hit"),
            "source_file_coverage": item.get("source_file_coverage"),
            "content_type_hit": item.get("content_type_hit"),
            "answer_pass": item.get("answer_pass"),
            "must_include_score": item.get("must_include_score"),
            "elapsed_ms": item.get("elapsed_ms"),
            "expected_source_files": ";".join(expected_files(item)),
            "top_source_files": ";".join(top_source_files(item, 5)),
        }
        for k in k_values:
            row[f"hit_at_{k}"] = "" if rank is None else rank <= k
            row[f"source_coverage_at_{k}"] = source_coverage_at_k(item, k)
        rows.append(_rounded(row))
    return rows


def expected_files(result: dict[str, Any]) -> list[str]:
    return [item for item in result.get("expected_source_files") or [] if item]


def first_source_rank(result: dict[str, Any]) -> int | None:
    expected = set(expected_files(result))
    if not expected:
        return None
    for index, doc in enumerate(result.get("retrieved_documents") or [], start=1):
        if doc.get("source_file") in expected:
            return index
    return None


def source_coverage_at_k(result: dict[str, Any], k: int) -> float | None:
    expected = set(expected_files(result))
    if not expected:
        return None
    retrieved = {
        doc.get("source_file")
        for doc in (result.get("retrieved_documents") or [])[:k]
        if doc.get("source_file")
    }
    return len(expected & retrieved) / len(expected)


def top_source_files(result: dict[str, Any], limit: int) -> list[str]:
    files = []
    for doc in (result.get("retrieved_documents") or [])[:limit]:
        source_file = doc.get("source_file")
        if source_file:
            files.append(source_file)
    return files


def outcome_for(result: dict[str, Any]) -> str:
    if result.get("error"):
        return "error"
    if not result.get("answerable", True):
        return "pass" if result.get("answer_pass") else "refusal_fail"
    if expected_files(result) and not result.get("source_file_hit"):
        return "retrieval_miss"
    if result.get("content_type_hit") is False:
        return "content_type_miss"
    if result.get("answer_pass") is False:
        return "answer_or_metric_fail"
    return "pass"


def _dataset_path(report: dict[str, Any]) -> Path | None:
    dataset = report.get("dataset")
    if not dataset:
        return None
    path = Path(dataset)
    return path if path.exists() else None


def _label_for(path: Path, report: dict[str, Any], used: set[str]) -> str:
    config = report.get("config") or {}
    if config.get("rerank") is False:
        base = "no-rerank"
    elif config.get("rerank") is True:
        base = "rerank"
    else:
        base = "default"
    label = base
    if label in used:
        label = f"{base}-{path.stem.replace('rag_eval_', '')}"
    used.add(label)
    return label


def _rate(values: Any) -> float | None:
    items = list(values)
    return sum(1 for item in items if item) / len(items) if items else None


def _mean(values: Any) -> float | None:
    items = [item for item in values if item is not None]
    return sum(items) / len(items) if items else None


def _rounded(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: round(value, 4) if isinstance(value, float) else value
        for key, value in row.items()
    }

