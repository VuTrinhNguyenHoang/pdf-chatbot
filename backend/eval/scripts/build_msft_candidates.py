#!/usr/bin/env python3
"""Extract Docling chunks from the MSFT annual-report PDFs for eval authoring.

This script does not write to Supabase. It uses the same parser modules as the
application and emits compact JSONL candidates that are easier to inspect when
adding new eval questions.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
DEFAULT_DOCS_DIR = BACKEND / "test_docs" / "NASDAQ_MSFT"
DEFAULT_OUTPUT = BACKEND / "eval" / "artifacts" / "msft_candidates.jsonl"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def configure_parser_env() -> None:
    load_env(BACKEND / ".env")
    os.environ["DOCLING_OCR"] = "false"
    os.environ["ENABLE_IMAGE_EXTRACTION"] = "false"
    os.environ["ENABLE_IMAGE_DESCRIPTIONS"] = "false"


def backend_imports() -> Any:
    sys.path.insert(0, str(BACKEND))
    from src.ingestion_graph.docling_parser import parse_sources_with_docling

    return parse_sources_with_docling


def make_source(path: Path) -> dict[str, str]:
    return {
        "filename": path.name,
        "mimeType": "application/pdf",
        "contentBase64": base64.b64encode(path.read_bytes()).decode("ascii"),
    }


def compact_text(value: str, max_chars: int) -> str:
    return " ".join((value or "").split())[:max_chars]


def candidate_record(doc: Any, path: Path) -> dict[str, Any]:
    metadata = doc.metadata or {}
    return {
        "source_file": metadata.get("source_file") or path.name,
        "chunk_index": metadata.get("chunk_index"),
        "content_type": metadata.get("content_type", "text"),
        "page_start": metadata.get("page_start"),
        "page_end": metadata.get("page_end"),
        "title": metadata.get("table_title")
        or metadata.get("image_title")
        or metadata.get("title"),
        "uuid": metadata.get("uuid"),
        "preview": compact_text(doc.page_content, 700),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-dir", type=Path, default=DEFAULT_DOCS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=0, help="Optional max PDFs to parse")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_parser_env()
    parse_sources_with_docling = backend_imports()

    pdfs = sorted(args.docs_dir.glob("*.pdf"))
    if args.limit > 0:
        pdfs = pdfs[: args.limit]
    if not pdfs:
        raise SystemExit(f"No PDFs found in {args.docs_dir}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with args.output.open("w", encoding="utf-8") as handle:
        for pdf in pdfs:
            docs = parse_sources_with_docling([make_source(pdf)])
            for doc in docs:
                handle.write(json.dumps(candidate_record(doc, pdf), ensure_ascii=False) + "\n")
                count += 1
            print(f"{pdf.name}: {len(docs)} candidates")

    print(f"Wrote {count} candidates to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
