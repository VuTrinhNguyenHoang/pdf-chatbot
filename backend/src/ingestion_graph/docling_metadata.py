import hashlib

from docling.chunking import DocChunk
from docling.datamodel.base_models import DocItemLabel


def content_type(labels: set[DocItemLabel]) -> str:
    if DocItemLabel.TABLE in labels:
        return "table"
    if DocItemLabel.PICTURE in labels:
        return "image"
    return "text"


def extract_pages(doc_items) -> list[int]:
    pages = []
    for item in doc_items:
        for prov in getattr(item, "prov", []):
            if hasattr(prov, "page_no"):
                pages.append(int(prov.page_no))
    return pages


def extract_title(chunk: DocChunk) -> str | None:
    captions: list[str] = chunk.meta.captions or []
    headings: list[str] = chunk.meta.headings or []
    return (captions[0] if captions else None) or (headings[-1] if headings else None)


def extract_bboxes(doc_items) -> list[dict]:
    bboxes = []
    for item in doc_items:
        for prov in getattr(item, "prov", []):
            bbox = getattr(prov, "bbox", None)
            if bbox:
                bboxes.append({"l": bbox.l, "t": bbox.t, "r": bbox.r, "b": bbox.b})
    return bboxes


def stable_id(source_file: str, index: int, content: str) -> str:
    raw = f"{source_file}:{index}:{content[:500]}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
