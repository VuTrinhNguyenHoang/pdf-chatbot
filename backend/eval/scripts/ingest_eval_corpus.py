#!/usr/bin/env python3
"""Ingest the MSFT eval PDFs into the configured Supabase vector store."""

from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
DEFAULT_DOCS_DIR = BACKEND / "test_docs" / "NASDAQ_MSFT"
DELETE_BATCH_SIZE = 100
SELECT_PAGE_SIZE = 500


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def configure_env(include_images: bool, use_env_docling_settings: bool) -> None:
    load_env(BACKEND / ".env")
    if use_env_docling_settings:
        return
    os.environ["DOCLING_OCR"] = "false"
    os.environ["ENABLE_IMAGE_DESCRIPTIONS"] = "false"
    os.environ["ENABLE_IMAGE_EXTRACTION"] = "true" if include_images else "false"


def backend_imports():
    sys.path.insert(0, str(BACKEND))
    from src.ingestion_graph.graph import graph
    from src.shared import settings

    return graph, settings


def make_sources(paths: Iterable[Path]) -> list[dict[str, str]]:
    sources = []
    for path in paths:
        sources.append(
            {
                "filename": path.name,
                "mimeType": "application/pdf",
                "contentBase64": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
        )
    return sources


def supabase_client(settings):
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured")
    from supabase import create_client

    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def find_document_ids(supabase, filenames: set[str]) -> list[str]:
    ids: list[str] = []
    start = 0
    while True:
        response = (
            supabase.from_("documents")
            .select("id, metadata")
            .order("id", desc=False)
            .range(start, start + SELECT_PAGE_SIZE - 1)
            .execute()
        )
        rows = response.data or []
        for row in rows:
            metadata = row.get("metadata") or {}
            if metadata.get("source_file") in filenames or metadata.get("filename") in filenames:
                ids.append(row["id"])
        if len(rows) < SELECT_PAGE_SIZE:
            break
        start += SELECT_PAGE_SIZE
    return ids


def delete_existing_rows(settings, filenames: set[str]) -> int:
    supabase = supabase_client(settings)
    ids = find_document_ids(supabase, filenames)
    for start in range(0, len(ids), DELETE_BATCH_SIZE):
        batch = ids[start : start + DELETE_BATCH_SIZE]
        supabase.from_("documents").delete().in_("id", batch).execute()
    return len(ids)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-dir", type=Path, default=DEFAULT_DOCS_DIR)
    parser.add_argument("--delete-existing", action="store_true")
    parser.add_argument("--include-images", action="store_true")
    parser.add_argument(
        "--use-env-docling-settings",
        action="store_true",
        help="Use DOCLING_* and ENABLE_IMAGE_* values from backend/.env instead of lightweight eval defaults",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_env(args.include_images, args.use_env_docling_settings)
    graph, settings = backend_imports()

    pdfs = sorted(args.docs_dir.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in {args.docs_dir}")

    filenames = {path.name for path in pdfs}
    print("Eval PDFs:")
    for path in pdfs:
        print(f"- {path}")

    if args.dry_run:
        return 0

    if args.delete_existing:
        deleted = delete_existing_rows(settings, filenames)
        print(f"Deleted {deleted} existing Supabase rows for eval filenames")

    result = graph.invoke(
        {"sources": make_sources(pdfs)},
        config={"configurable": {"retrieverProvider": "supabase"}},
    )
    print(f"Ingestion completed. Final graph keys: {sorted(result.keys())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
