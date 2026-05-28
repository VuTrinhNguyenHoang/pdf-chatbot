#!/usr/bin/env python3
"""Run the MSFT RAG eval dataset against the local retrieval graph.

The script invokes the same backend retrieval graph used by the app. It records
retrieved source files, final answer text, and lightweight pass/fail metrics.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
DEFAULT_DATASET = BACKEND / "eval" / "datasets" / "msft_annual_reports_min.jsonl"
DEFAULT_RUNS_DIR = BACKEND / "eval" / "runs"
REFUSAL_TERMS = (
    "not provided",
    "not available",
    "not contain",
    "do not contain",
    "cannot be answered",
    "insufficient",
    "không có",
    "không đủ",
)


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def backend_imports():
    load_env(BACKEND / ".env")
    sys.path.insert(0, str(BACKEND))
    from src.retrieval_graph.graph import graph
    from src.shared import settings

    return graph, settings


def load_dataset(path: Path) -> list[dict[str, Any]]:
    samples = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            samples.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
    return samples


def normalize(value: str) -> str:
    value = value.casefold()
    value = value.replace("$", "")
    value = value.replace(",", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def contains_term(answer: str, term: str) -> bool:
    answer_norm = normalize(answer)
    term_norm = normalize(term)
    return term_norm in answer_norm


def message_content(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    return str(content)


def document_record(doc: Any) -> dict[str, Any]:
    metadata = getattr(doc, "metadata", None) or {}
    return {
        "source_file": metadata.get("source_file") or metadata.get("filename") or metadata.get("source"),
        "content_type": metadata.get("content_type", "text"),
        "page_start": metadata.get("page_start"),
        "page_end": metadata.get("page_end"),
        "title": metadata.get("table_title") or metadata.get("image_title") or metadata.get("title"),
        "uuid": metadata.get("uuid"),
        "preview": " ".join((getattr(doc, "page_content", "") or "").split())[:280],
    }


def expected_files(sample: dict[str, Any]) -> list[str]:
    retrieval = sample.get("retrieval_expectations") or {}
    files = retrieval.get("expected_source_files")
    if files is not None:
        return list(files)
    return sorted(
        {
            item["source_file"]
            for item in sample.get("source_expectations", [])
            if item.get("source_file")
        }
    )


def source_metrics(sample: dict[str, Any], docs: list[dict[str, Any]]) -> dict[str, Any]:
    expected = expected_files(sample)
    retrieved = [doc.get("source_file") for doc in docs if doc.get("source_file")]
    if not expected:
        return {
            "expected_source_files": expected,
            "retrieved_source_files": retrieved,
            "source_file_hit": None,
            "source_file_coverage": None,
        }

    retrieved_set = set(retrieved)
    hits = [name for name in expected if name in retrieved_set]
    return {
        "expected_source_files": expected,
        "retrieved_source_files": retrieved,
        "source_file_hit": bool(hits),
        "source_file_coverage": len(hits) / len(expected),
    }


def content_type_hit(sample: dict[str, Any], docs: list[dict[str, Any]]) -> bool | None:
    expectations = [item for item in sample.get("source_expectations", []) if item.get("content_type")]
    if not expectations:
        return None
    for expected in expectations:
        for doc in docs:
            same_file = not expected.get("source_file") or expected.get("source_file") == doc.get("source_file")
            same_type = expected.get("content_type") == doc.get("content_type")
            if same_file and same_type:
                return True
    return False


def answer_metrics(sample: dict[str, Any], answer: str) -> dict[str, Any]:
    must_include = list(sample.get("must_include") or [])
    present = [term for term in must_include if contains_term(answer, term)]
    answerable = bool(sample.get("answerable", True))

    if answerable:
        must_include_score = len(present) / len(must_include) if must_include else None
        return {
            "must_include_present": present,
            "must_include_score": must_include_score,
            "answer_pass": must_include_score is None or must_include_score == 1.0,
        }

    answer_norm = normalize(answer)
    acceptable = [normalize(item) for item in sample.get("acceptable_answers", [])]
    refusal_hit = any(term in answer_norm for term in REFUSAL_TERMS) or any(
        item and item in answer_norm for item in acceptable
    )
    return {
        "must_include_present": present,
        "must_include_score": None,
        "answer_pass": refusal_hit,
    }


def run_sample(graph: Any, sample: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    state = graph.invoke({"query": sample["question"]}, config={"configurable": config})
    elapsed_ms = round((time.perf_counter() - started) * 1000)

    messages = state.get("messages") or []
    answer = message_content(messages[-1]) if messages else ""
    docs = [document_record(doc) for doc in (state.get("documents") or [])]

    result = {
        "id": sample["id"],
        "question": sample["question"],
        "answerable": sample.get("answerable", True),
        "route": state.get("route"),
        "iteration_count": state.get("iteration_count"),
        "elapsed_ms": elapsed_ms,
        "answer": answer,
        "retrieved_documents": docs,
    }
    result.update(source_metrics(sample, docs))
    result["content_type_hit"] = content_type_hit(sample, docs)
    result.update(answer_metrics(sample, answer))
    return result


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [item for item in results if item.get("answerable")]
    source_scored = [item for item in answerable if item.get("source_file_hit") is not None]
    type_scored = [item for item in answerable if item.get("content_type_hit") is not None]
    answer_scored = [item for item in results if item.get("answer_pass") is not None]

    def rate(items: list[dict[str, Any]], key: str) -> float | None:
        if not items:
            return None
        return sum(1 for item in items if item.get(key)) / len(items)

    timed = [item for item in results if isinstance(item.get("elapsed_ms"), int)]
    return {
        "sample_count": len(results),
        "answerable_count": len(answerable),
        "source_file_hit_rate": rate(source_scored, "source_file_hit"),
        "content_type_hit_rate": rate(type_scored, "content_type_hit"),
        "answer_pass_rate": rate(answer_scored, "answer_pass"),
        "avg_elapsed_ms": round(sum(item["elapsed_ms"] for item in timed) / len(timed))
        if timed
        else None,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--query-model", default=None)
    parser.add_argument("--k", type=int, default=None)
    parser.add_argument("--candidate-k", type=int, default=None)
    parser.add_argument("--rerank", dest="rerank", action="store_true", default=None)
    parser.add_argument("--no-rerank", dest="rerank", action="store_false")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    graph, settings = backend_imports()
    samples = load_dataset(args.dataset)
    if args.limit > 0:
        samples = samples[: args.limit]

    config: dict[str, Any] = {"retrieverProvider": "supabase"}
    if args.query_model or settings.CHAT_MODEL:
        config["queryModel"] = args.query_model or settings.CHAT_MODEL
    if args.k is not None:
        config["k"] = args.k
    if args.candidate_k is not None:
        config["candidateK"] = args.candidate_k
    if args.rerank is not None:
        config["rerank"] = args.rerank

    results = []
    for index, sample in enumerate(samples, start=1):
        print(f"[{index}/{len(samples)}] {sample['id']}")
        try:
            results.append(run_sample(graph, sample, config))
        except Exception as exc:  # keep the run report useful even when one sample fails
            results.append(
                {
                    "id": sample.get("id"),
                    "question": sample.get("question"),
                    "answerable": sample.get("answerable", True),
                    "error": f"{type(exc).__name__}: {exc}",
                    "answer_pass": False,
                }
            )
            print(f"  ERROR: {type(exc).__name__}: {exc}")

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(args.dataset),
        "config": config,
        "summary": summarize(results),
        "results": results,
    }

    output = args.output
    if output is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = DEFAULT_RUNS_DIR / f"rag_eval_{stamp}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    print(f"Wrote report to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
