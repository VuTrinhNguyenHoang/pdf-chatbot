import base64
import hashlib
import tempfile
from pathlib import Path

from docling.chunking import HybridChunker
from langchain_core.documents import Document
from langchain_docling import DoclingLoader
from langchain_docling.loader import ExportType

from src.ingestion_graph.state import IndexSource


def parse_sources_with_docling(sources: list[IndexSource]) -> list[Document]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        paths = [_write_source(source, Path(tmp_dir)) for source in sources]
        loader = DoclingLoader(
            file_path=[str(path) for path in paths],
            export_type=ExportType.DOC_CHUNKS,
            chunker=HybridChunker(repeat_table_header=True),
        )
        return [_normalize_doc(index, doc) for index, doc in enumerate(loader.load())]

def _write_source(source: IndexSource, tmp_dir: Path) -> Path:
    filename = Path(source["filename"]).name
    path = tmp_dir / filename
    path.write_bytes(base64.b64decode(source["contentBase64"]))
    return path

def _normalize_doc(index: int, doc: Document) -> Document:
    raw_metadata = dict(doc.metadata or {})
    dl_meta = raw_metadata.get("dl_meta") or {}

    labels = _extract_labels(dl_meta)
    pages = _extract_pages(dl_meta)
    content_type = _content_type(labels)
    title = _title(dl_meta)
    source_file = _source_file(raw_metadata, dl_meta)
    bboxes = _extract_bboxes(dl_meta)

    metadata = {
        "uuid": _stable_id(source_file, index, doc.page_content),
        "parser": "docling",
        "source": source_file,
        "filename": source_file,
        "source_file": source_file,
        "chunk_index": index,
        "content_type": content_type,
        "page_start": min(pages) if pages else None,
        "page_end": max(pages) if pages else None,
        "bbox": bboxes[:5],
        "title": title,
        "title_confidence": "docling" if title else "missing",
        "table_title": title if content_type == "table" else None,
        "image_title": title if content_type == "image" else None,
        "docling_labels": sorted(labels),
    }
    return Document(page_content=doc.page_content, metadata=metadata)

def _extract_bboxes(dl_meta: dict) -> list[dict]:
    bboxes = []
    for item in dl_meta.get("doc_items", []):
        for prov in item.get("prov", []):
            bbox = prov.get("bbox")
            if bbox:
                bboxes.append(bbox)
    return bboxes

def _source_file(metadata: dict, dl_meta: dict) -> str | None:
    origin = dl_meta.get("origin") or {}
    if origin.get("filename"):
        return origin["filename"]

    source = metadata.get("source")
    if source:
        return Path(str(source)).name

    return None

def _extract_labels(dl_meta: dict) -> set[str]:
    return {
        item.get("label", "")
        for item in dl_meta.get("doc_items", [])
        if item.get("label")
    }

def _extract_pages(dl_meta: dict) -> list[int]:
    pages = []
    for item in dl_meta.get("doc_items", []):
        for prov in item.get("prov", []):
            if "page_no" in prov:
                pages.append(int(prov["page_no"]))
    return pages

def _content_type(labels: set[str]) -> str:
    if "table" in labels:
        return "table"
    if "picture" in labels or "figure" in labels:
        return "image"
    return "text"

def _title(dl_meta: dict) -> str | None:
    captions = dl_meta.get("captions") or []
    headings = dl_meta.get("headings") or []
    return (captions[0] if captions else None) or (headings[-1] if headings else None)

def _stable_id(source_file: str | None, index: int, content: str) -> str:
    raw = f"{source_file or ''}:{index}:{content[:500]}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
