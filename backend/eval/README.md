# RAG Evaluation

This folder contains a small self-authored RAG evaluation set for the PDF Chatbot.
The current dataset targets the five Microsoft annual-report PDFs under
`backend/test_docs/NASDAQ_MSFT`.

## Files

```text
backend/eval/
├── datasets/
│   └── msft_annual_reports_min.jsonl
├── scripts/
│   ├── build_msft_candidates.py
│   ├── ingest_eval_corpus.py
│   ├── run_rag_eval.py
│   └── analyze_rag_eval.py
└── runs/
```

`msft_annual_reports_min.jsonl` has 15 samples:

- 10 single-document questions
- 3 cross-year comparison questions
- 2 unanswerable questions

Each sample stores the question, expected answer, required answer terms, expected
source files, optional expected content type, tags, difficulty, and whether the
question is answerable from the uploaded PDFs.

## Recommended Workflow

Run commands from the repository root.

1. Activate the backend environment.

```bash
source .venv/bin/activate
```

2. Optional: inspect chunks that can be used to author more questions.

```bash
PYTHONPATH=backend .venv/bin/python backend/eval/scripts/build_msft_candidates.py
```

The output is written to `backend/eval/artifacts/msft_candidates.jsonl`.

3. Ingest the five MSFT PDFs into Supabase.

```bash
PYTHONPATH=backend .venv/bin/python backend/eval/scripts/ingest_eval_corpus.py --delete-existing
```

By default, the script disables OCR, image extraction, and vision descriptions for
speed. The current eval questions target text and tables, not image previews. Use
`--include-images` or `--use-env-docling-settings` when you intentionally want to
evaluate the heavier ingestion configuration.

4. Run the eval with the default retrieval settings.

```bash
PYTHONPATH=backend .venv/bin/python backend/eval/scripts/run_rag_eval.py
```

5. Run a no-rerank ablation.

```bash
PYTHONPATH=backend .venv/bin/python backend/eval/scripts/run_rag_eval.py --no-rerank
```

Reports are written to `backend/eval/runs/rag_eval_<timestamp>.json`.

6. Analyze saved reports and generate figures.

```bash
PYTHONPATH=backend .venv/bin/python backend/eval/scripts/analyze_rag_eval.py --latest 2
```

The analysis script reads existing JSON reports, so it does not call OpenAI,
Supabase, or the LangGraph server. It writes `summary.md`, `summary.csv`,
`per_sample.csv`, and SVG figures under `backend/eval/artifacts/`.

## Metrics

The runner records lightweight metrics that fit the current project surface:

- `source_file_hit_rate`: at least one expected source file was retrieved.
- `source_hit_at_k`: at least one expected source file appeared in the top `k`
  saved retrieved documents.
- `mrr`: mean reciprocal rank of the first expected source file in the saved
  retrieved-document order.
- `content_type_hit_rate`: an expected text/table source type was retrieved.
- `answer_pass_rate`: all `must_include` terms were found for answerable
  samples, or the answer used a refusal phrase for unanswerable samples.
- `avg_elapsed_ms`: average graph invocation latency.

`source_hit_at_k` and `mrr` are post-run metrics. They can be computed from the
saved reports as long as `k` is not larger than the retrieved-document list saved
by the original eval run.

These metrics are intentionally simple. They are meant to catch regressions in
retrieval and grounded answering without adding a separate evaluation framework.

## Notes

Use a clean Supabase project or delete rows for the five MSFT filenames before
running the eval. The app uses one shared `documents` table and ingestion does
not upsert by document UUID, so stale or duplicate rows can contaminate scores.
