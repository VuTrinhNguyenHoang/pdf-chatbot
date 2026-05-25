import base64
import hashlib
import io
import os
import tempfile
from pathlib import Path
from typing import Optional

from docling.chunking import DocChunk, HybridChunker
from docling.datamodel.base_models import DocItemLabel
from docling.datamodel.document import PictureItem, TableItem
from docling.document_converter import DocumentConverter
from langchain_core.documents import Document
from openai import OpenAI

from src.ingestion_graph.state import IndexSource

VISION_MODEL = "gpt-4o-mini"
DEFAULT_MAX_IMAGE_DESCRIPTIONS_PER_FILE = 20
VISION_PROMPT = (
    "Describe this image concisely (2-4 sentences). Include: what the image shows, "
    "any visible text, numbers, or labels, and the insight it provides in a document "
    "context (e.g. trend of a chart, structure of a diagram, subject of a photo)."
)


def parse_sources_with_docling(sources: list[IndexSource]) -> list[Document]:
    converter = DocumentConverter()
    chunker = HybridChunker(repeat_table_header=True)
    vision = OpenAI() if _image_descriptions_enabled() else None
    image_cache: dict[str, str] = {}

    all_docs: list[Document] = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        for source in sources:
            path = _write_source(source, Path(tmp_dir))
            result = converter.convert(str(path))
            dl_doc = result.document
            chunks = list(chunker.chunk(dl_doc))
            seen_tables: set[str] = set()
            image_budget = {"remaining": _max_image_descriptions_per_file()}
            for idx, chunk in enumerate(chunks):
                doc = _chunk_to_document(
                    chunk,
                    idx,
                    source["filename"],
                    dl_doc,
                    vision,
                    image_cache,
                    image_budget,
                    seen_tables,
                )
                if doc is not None:
                    all_docs.append(doc)

    return all_docs


# ── helpers ──────────────────────────────────────────────────────────────────

def _write_source(source: IndexSource, tmp_dir: Path) -> Path:
    filename = Path(source["filename"]).name
    path = tmp_dir / filename
    path.write_bytes(base64.b64decode(source["contentBase64"]))
    return path


def _chunk_to_document(
    chunk: DocChunk,
    index: int,
    filename: str,
    dl_doc,
    vision: OpenAI | None,
    image_cache: dict[str, str],
    image_budget: dict[str, int],
    seen_tables: set[str] | None = None,
) -> Document | None:
    doc_items = list(chunk.meta.doc_items or [])
    labels = {item.label for item in doc_items}
    content_type = _content_type(labels)
    pages = _extract_pages(doc_items)
    title = _extract_title(chunk)
    bboxes = _extract_bboxes(doc_items)
    source_file = Path(filename).name

    if content_type == "image":
        page_content = _describe_image(
            doc_items,
            dl_doc,
            vision,
            chunk.text,
            image_cache,
            image_budget,
        )
    elif content_type == "table":
        page_content = _extract_table_markdown(doc_items, dl_doc, chunk.text)
        if seen_tables is not None:
            if page_content in seen_tables:
                return None
            seen_tables.add(page_content)
    else:
        page_content = chunk.text or ""

    metadata = {
        "uuid": _stable_id(source_file, index, page_content),
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
        "docling_labels": sorted(l.value for l in labels),
    }
    return Document(page_content=page_content, metadata=metadata)


def _extract_table_markdown(doc_items, dl_doc, fallback: str) -> str:
    for item in doc_items:
        if isinstance(item, TableItem):
            try:
                md = item.export_to_markdown(dl_doc)
                if md:
                    return md
            except Exception:
                pass
    return fallback or ""


def _describe_image(
    doc_items,
    dl_doc,
    vision: OpenAI | None,
    fallback: str,
    image_cache: dict[str, str],
    image_budget: dict[str, int],
) -> str:
    if vision is None:
        return _image_fallback(fallback)

    for item in doc_items:
        if not isinstance(item, PictureItem):
            continue
        try:
            pil_img = item.get_image(dl_doc)
            if pil_img is None:
                continue
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            image_bytes = buf.getvalue()
            image_hash = hashlib.sha1(image_bytes).hexdigest()

            if image_hash in image_cache:
                return image_cache[image_hash]
            if image_budget["remaining"] <= 0:
                return _image_fallback(fallback)

            image_budget["remaining"] -= 1
            b64 = base64.b64encode(image_bytes).decode()
            resp = vision.chat.completions.create(
                model=VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }],
                max_tokens=300,
            )
            description = (resp.choices[0].message.content or "").strip()
            if description:
                image_cache[image_hash] = description
                return description
        except Exception:
            pass
    return _image_fallback(fallback)


def _image_fallback(fallback: str) -> str:
    return fallback or "Image extracted from the document."


def _image_descriptions_enabled() -> bool:
    value = os.getenv("ENABLE_IMAGE_DESCRIPTIONS", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _max_image_descriptions_per_file() -> int:
    value = os.getenv("MAX_IMAGE_DESCRIPTIONS_PER_FILE")
    if not value:
        return DEFAULT_MAX_IMAGE_DESCRIPTIONS_PER_FILE
    try:
        return max(0, int(value))
    except ValueError:
        return DEFAULT_MAX_IMAGE_DESCRIPTIONS_PER_FILE


def _content_type(labels: set[DocItemLabel]) -> str:
    if DocItemLabel.TABLE in labels:
        return "table"
    if DocItemLabel.PICTURE in labels:
        return "image"
    return "text"


def _extract_pages(doc_items) -> list[int]:
    pages = []
    for item in doc_items:
        for prov in getattr(item, "prov", []):
            if hasattr(prov, "page_no"):
                pages.append(int(prov.page_no))
    return pages


def _extract_title(chunk: DocChunk) -> Optional[str]:
    captions: list[str] = chunk.meta.captions or []
    headings: list[str] = chunk.meta.headings or []
    return (captions[0] if captions else None) or (headings[-1] if headings else None)


def _extract_bboxes(doc_items) -> list[dict]:
    bboxes = []
    for item in doc_items:
        for prov in getattr(item, "prov", []):
            bbox = getattr(prov, "bbox", None)
            if bbox:
                bboxes.append({"l": bbox.l, "t": bbox.t, "r": bbox.r, "b": bbox.b})
    return bboxes


def _stable_id(source_file: str, index: int, content: str) -> str:
    raw = f"{source_file}:{index}:{content[:500]}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
