import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from langchain_core.documents import Document


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
CURRENT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "datapdf"
RESULTS_DIR = CURRENT_DIR / "results"

sys.path.insert(0, str(CURRENT_DIR))
sys.path.insert(0, str(BACKEND_DIR))

from experimental_graph import graph  # noqa: E402
from experimental_retrieval import make_eval_retriever  # noqa: E402


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)
    return normalized.split() if normalized else []


def compute_token_f1(reference: str, prediction: str) -> float:
    ref_tokens = tokenize(reference)
    pred_tokens = tokenize(prediction)
    if not ref_tokens or not pred_tokens:
        return 0.0

    ref_counts: dict[str, int] = {}
    pred_counts: dict[str, int] = {}
    for token in ref_tokens:
        ref_counts[token] = ref_counts.get(token, 0) + 1
    for token in pred_tokens:
        pred_counts[token] = pred_counts.get(token, 0) + 1

    overlap = 0
    for token, count in ref_counts.items():
        overlap += min(count, pred_counts.get(token, 0))

    if overlap == 0:
        return 0.0

    precision = overlap / len(pred_tokens)
    recall = overlap / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def compute_exact_match(reference: str, prediction: str) -> bool:
    return normalize_text(reference) == normalize_text(prediction)


def chunk_text(text: str, chunk_size: int = 1800, overlap: int = 250) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        chunks.append(cleaned[start:end])
        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)
    return chunks


def contains_abstention(answer: str) -> bool:
    normalized = normalize_text(answer)
    abstention_markers = (
        "i don t know",
        "i do not know",
        "don t know",
        "do not know",
        "cannot determine",
        "not enough information",
    )
    return any(marker in normalized for marker in abstention_markers)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def apply_limit(rows: list[dict[str, Any]], limit: int | None) -> list[dict[str, Any]]:
    if limit is None or limit <= 0:
        return rows
    return rows[:limit]


def build_eval_documents(dataset_name: str) -> list[Document]:
    rows = load_jsonl(DATA_DIR / "documents.jsonl")
    docs: list[Document] = []
    for row in rows:
        for chunk_id, chunk in enumerate(chunk_text(row["text"])):
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "eval_dataset": dataset_name,
                        "document_index": str(row["index"]),
                        "source_url": row.get("source_url", ""),
                        "chunk_id": chunk_id,
                    },
                )
            )
    return docs


@dataclass
class RetrievalCaseResult:
    question: str
    document_index: str
    hit: bool
    top1_correct: bool
    reciprocal_rank: float
    retrieved_document_indexes: list[str]


@dataclass
class AnswerCaseResult:
    question: str
    expected: str
    predicted: str
    exact_match: bool
    token_f1: float
    route: str | None


def make_config(dataset_name: str, k: int, query_model: str) -> dict[str, Any]:
    candidate_k = int(os.getenv("EVAL_CANDIDATE_K", str(max(k, 8) * 2)))
    return {
        "configurable": {
            "retrieverProvider": "supabase",
            "filterKwargs": {"eval_dataset": dataset_name},
            "k": k,
            "candidateK": candidate_k,
            "queryModel": query_model,
        }
    }


def clear_eval_dataset(dataset_name: str) -> None:
    retriever = make_eval_retriever(
        k=5,
        candidate_k=8,
        filter_kwargs={"eval_dataset": dataset_name},
    )
    retriever.vector_store._client.table("documents").delete().eq(
        "metadata->>eval_dataset", dataset_name
    ).execute()


def ingest_eval_documents(dataset_name: str) -> dict[str, Any]:
    docs = build_eval_documents(dataset_name)
    if not docs:
        raise ValueError("No evaluation documents were created.")

    clear_eval_dataset(dataset_name)
    retriever = make_eval_retriever(
        k=5,
        candidate_k=8,
        filter_kwargs={"eval_dataset": dataset_name},
    )
    inserted_ids = retriever.add_documents(docs)
    return {
        "documents": len(docs),
        "inserted_ids": len(inserted_ids),
    }


def evaluate_retrieval(dataset_name: str, dataset_file: str, k: int) -> dict[str, Any]:
    limit = int(os.getenv("EVAL_LIMIT", "0"))
    rows = apply_limit(load_jsonl(DATA_DIR / dataset_file), limit)
    config = make_config(dataset_name, k, "openai/gpt-4o-mini")
    candidate_k = int(config["configurable"]["candidateK"])
    retriever = make_eval_retriever(
        k=k,
        candidate_k=candidate_k,
        filter_kwargs={"eval_dataset": dataset_name},
    )

    cases: list[RetrievalCaseResult] = []
    for row in rows:
        print(f"[retrieval] {dataset_file}: {row['question'][:80]}", flush=True)
        matches = retriever.invoke(row["question"], limit=k)
        retrieved_indexes = [str(doc.metadata.get("document_index", "")) for doc in matches]
        top1_correct = bool(retrieved_indexes) and (
            retrieved_indexes[0] == str(row["document_index"])
        )

        reciprocal_rank = 0.0
        for rank, retrieved_index in enumerate(retrieved_indexes, start=1):
            if retrieved_index == str(row["document_index"]):
                reciprocal_rank = 1.0 / rank
                break

        cases.append(
            RetrievalCaseResult(
                question=row["question"],
                document_index=str(row["document_index"]),
                hit=reciprocal_rank > 0,
                top1_correct=top1_correct,
                reciprocal_rank=reciprocal_rank,
                retrieved_document_indexes=retrieved_indexes,
            )
        )

    total = len(cases) or 1
    return {
        "dataset": dataset_file,
        "questions": len(cases),
        "accuracy": sum(1 for case in cases if case.top1_correct) / total,
        "top1_accuracy": sum(1 for case in cases if case.top1_correct) / total,
        "recall_at_k": sum(1 for case in cases if case.hit) / total,
        "mrr": sum(case.reciprocal_rank for case in cases) / total,
        "cases": [asdict(case) for case in cases],
    }


def evaluate_answers(
    dataset_name: str,
    dataset_file: str,
    k: int,
    query_model: str,
) -> dict[str, Any]:
    limit = int(os.getenv("EVAL_LIMIT", "0"))
    rows = apply_limit(load_jsonl(DATA_DIR / dataset_file), limit)
    config = make_config(dataset_name, k, query_model)
    cases: list[AnswerCaseResult] = []
    started_at = time.perf_counter()

    for row in rows:
        print(f"[answer] {dataset_file}: {row['question'][:80]}", flush=True)
        state = graph.invoke({"query": row["question"]}, config=config)
        messages = state.get("messages", [])
        predicted = messages[-1].content if messages else ""
        cases.append(
            AnswerCaseResult(
                question=row["question"],
                expected=row["answer"],
                predicted=predicted,
                exact_match=compute_exact_match(row["answer"], predicted),
                token_f1=compute_token_f1(row["answer"], predicted),
                route=state.get("route"),
            )
        )

    elapsed = time.perf_counter() - started_at
    total = len(cases) or 1
    return {
        "dataset": dataset_file,
        "questions": len(cases),
        "accuracy": sum(1 for case in cases if case.exact_match) / total,
        "exact_match": sum(1 for case in cases if case.exact_match) / total,
        "mean_token_f1": mean(case.token_f1 for case in cases) if cases else 0.0,
        "mean_latency_seconds": elapsed / total,
        "cases": [asdict(case) for case in cases],
    }


def evaluate_no_answer(
    dataset_name: str,
    dataset_file: str,
    k: int,
    query_model: str,
) -> dict[str, Any]:
    limit = int(os.getenv("EVAL_LIMIT", "0"))
    rows = apply_limit(load_jsonl(DATA_DIR / dataset_file), limit)
    config = make_config(dataset_name, k, query_model)
    abstentions: list[dict[str, Any]] = []
    started_at = time.perf_counter()

    for row in rows:
        print(f"[no-answer] {dataset_file}: {row['question'][:80]}", flush=True)
        state = graph.invoke({"query": row["question"]}, config=config)
        messages = state.get("messages", [])
        predicted = messages[-1].content if messages else ""
        abstentions.append(
            {
                "question": row["question"],
                "predicted": predicted,
                "abstained": contains_abstention(predicted),
                "route": state.get("route"),
            }
        )

    elapsed = time.perf_counter() - started_at
    total = len(abstentions) or 1
    return {
        "dataset": dataset_file,
        "questions": len(abstentions),
        "accuracy": sum(1 for row in abstentions if row["abstained"]) / total,
        "abstention_rate": sum(1 for row in abstentions if row["abstained"]) / total,
        "mean_latency_seconds": elapsed / total,
        "cases": abstentions,
    }


def build_summary(results: dict[str, Any]) -> dict[str, Any]:
    retrieval_single = results["retrieval"]["single_passage_answer_questions.jsonl"]
    retrieval_multi = results["retrieval"]["multi_passage_answer_questions.jsonl"]
    answer_single = results["answers"]["single_passage_answer_questions.jsonl"]
    answer_multi = results["answers"]["multi_passage_answer_questions.jsonl"]
    no_answer = results["answers"]["no_answer_questions.jsonl"]

    return {
        "dataset_name": results["dataset_name"],
        "query_model": results["query_model"],
        "k": results["k"],
        "ingested_chunks": results["ingestion"]["documents"],
        "retrieval": {
            "single_accuracy": retrieval_single["accuracy"],
            "single_recall_at_k": retrieval_single["recall_at_k"],
            "single_mrr": retrieval_single["mrr"],
            "multi_accuracy": retrieval_multi["accuracy"],
            "multi_recall_at_k": retrieval_multi["recall_at_k"],
            "multi_mrr": retrieval_multi["mrr"],
        },
        "answers": {
            "single_accuracy": answer_single["accuracy"],
            "single_exact_match": answer_single["exact_match"],
            "single_mean_token_f1": answer_single["mean_token_f1"],
            "multi_accuracy": answer_multi["accuracy"],
            "multi_exact_match": answer_multi["exact_match"],
            "multi_mean_token_f1": answer_multi["mean_token_f1"],
            "no_answer_accuracy": no_answer["accuracy"],
            "no_answer_abstention_rate": no_answer["abstention_rate"],
        },
    }


def main() -> None:
    load_env_file(BACKEND_DIR / ".env")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    dataset_name = f"eval-{int(time.time())}"
    k = int(os.getenv("EVAL_K", "5"))
    query_model = os.getenv("EVAL_QUERY_MODEL", "openai/gpt-4o-mini")
    eval_mode = os.getenv("EVAL_MODE", "all")

    results: dict[str, Any] = {
        "dataset_name": dataset_name,
        "k": k,
        "query_model": query_model,
    }

    results["ingestion"] = ingest_eval_documents(dataset_name)
    if eval_mode in ("all", "retrieval"):
        results["retrieval"] = {
            "single_passage_answer_questions.jsonl": evaluate_retrieval(
                dataset_name, "single_passage_answer_questions.jsonl", k
            ),
            "multi_passage_answer_questions.jsonl": evaluate_retrieval(
                dataset_name, "multi_passage_answer_questions.jsonl", k
            ),
        }

    if eval_mode in ("all", "answers"):
        results["answers"] = {
            "single_passage_answer_questions.jsonl": evaluate_answers(
                dataset_name, "single_passage_answer_questions.jsonl", k, query_model
            ),
            "multi_passage_answer_questions.jsonl": evaluate_answers(
                dataset_name, "multi_passage_answer_questions.jsonl", k, query_model
            ),
            "no_answer_questions.jsonl": evaluate_no_answer(
                dataset_name, "no_answer_questions.jsonl", k, query_model
            ),
        }

    if eval_mode == "all":
        results["summary"] = build_summary(results)
    elif eval_mode == "retrieval":
        results["summary"] = {
            "dataset_name": dataset_name,
            "query_model": query_model,
            "k": k,
            "ingested_chunks": results["ingestion"]["documents"],
            "retrieval": {
                "single_accuracy": results["retrieval"][
                    "single_passage_answer_questions.jsonl"
                ]["accuracy"],
                "single_recall_at_k": results["retrieval"][
                    "single_passage_answer_questions.jsonl"
                ]["recall_at_k"],
                "single_mrr": results["retrieval"][
                    "single_passage_answer_questions.jsonl"
                ]["mrr"],
                "multi_accuracy": results["retrieval"][
                    "multi_passage_answer_questions.jsonl"
                ]["accuracy"],
                "multi_recall_at_k": results["retrieval"][
                    "multi_passage_answer_questions.jsonl"
                ]["recall_at_k"],
                "multi_mrr": results["retrieval"][
                    "multi_passage_answer_questions.jsonl"
                ]["mrr"],
            },
        }
    else:
        results["summary"] = {
            "dataset_name": dataset_name,
            "query_model": query_model,
            "k": k,
            "ingested_chunks": results["ingestion"]["documents"],
            "answers": {
                "single_accuracy": results["answers"][
                    "single_passage_answer_questions.jsonl"
                ]["accuracy"],
                "single_exact_match": results["answers"][
                    "single_passage_answer_questions.jsonl"
                ]["exact_match"],
                "single_mean_token_f1": results["answers"][
                    "single_passage_answer_questions.jsonl"
                ]["mean_token_f1"],
                "multi_accuracy": results["answers"][
                    "multi_passage_answer_questions.jsonl"
                ]["accuracy"],
                "multi_exact_match": results["answers"][
                    "multi_passage_answer_questions.jsonl"
                ]["exact_match"],
                "multi_mean_token_f1": results["answers"][
                    "multi_passage_answer_questions.jsonl"
                ]["mean_token_f1"],
                "no_answer_accuracy": results["answers"][
                    "no_answer_questions.jsonl"
                ]["accuracy"],
                "no_answer_abstention_rate": results["answers"][
                    "no_answer_questions.jsonl"
                ]["abstention_rate"],
            },
        }

    timestamp = int(time.time())
    output_path = RESULTS_DIR / f"eval_{timestamp}.json"
    output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(results["summary"], ensure_ascii=False, indent=2))
    print(f"Saved detailed results to {output_path}")


if __name__ == "__main__":
    main()
