from pathlib import Path

from docling.chunking import DocChunk
from docling.datamodel.base_models import DocItemLabel
from docling.datamodel.document import PictureItem
from langchain_core.documents import Document
from openai import OpenAI

from src.ingestion_graph.docling_images import (
    describe_image,
    extract_image_preview,
    image_data_url,
)
from src.ingestion_graph.docling_metadata import (
    content_type,
    extract_bboxes,
    extract_pages,
    extract_title,
    stable_id,
)
from src.ingestion_graph.docling_tables import extract_table_markdown
from src.shared import settings


def chunk_to_document(
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
    doc_type = content_type(labels)
    pages = extract_pages(doc_items)
    title = extract_title(chunk)
    bboxes = extract_bboxes(doc_items)
    source_file = Path(filename).name

    if doc_type == "image" and not settings.ENABLE_IMAGE_EXTRACTION:
        return None

    image_preview = extract_image_preview(doc_items, dl_doc) if doc_type == "image" else None

    if doc_type == "image":
        page_content = describe_image(
            image_preview,
            vision,
            chunk.text,
            image_cache,
            image_budget,
        )
    elif doc_type == "table":
        page_content = extract_table_markdown(doc_items, dl_doc, chunk.text)
        if seen_tables is not None:
            if page_content in seen_tables:
                return None
            seen_tables.add(page_content)
    else:
        page_content = chunk.text or ""

    metadata = {
        "uuid": stable_id(source_file, index, page_content),
        "parser": "docling",
        "source": source_file,
        "filename": source_file,
        "source_file": source_file,
        "chunk_index": index,
        "content_type": doc_type,
        "page_start": min(pages) if pages else None,
        "page_end": max(pages) if pages else None,
        "bbox": bboxes[:5],
        "title": title,
        "title_confidence": "docling" if title else "missing",
        "table_title": title if doc_type == "table" else None,
        "image_title": title if doc_type == "image" else None,
        "image_data_url": image_data_url(image_preview),
        "image_mime_type": image_preview.mime_type if image_preview else None,
        "image_extraction_status": image_preview.status if image_preview else None,
        "docling_labels": sorted(l.value for l in labels),
    }
    return Document(page_content=page_content, metadata=metadata)


def picture_to_document(
    picture: PictureItem,
    index: int,
    filename: str,
    dl_doc,
    vision: OpenAI | None,
    image_cache: dict[str, str],
    image_budget: dict[str, int],
) -> Document:
    source_file = Path(filename).name
    image_preview = extract_image_preview([picture], dl_doc)
    page_content = describe_image(image_preview, vision, "", image_cache, image_budget)
    pages = extract_pages([picture])

    return Document(
        page_content=page_content,
        metadata={
            "uuid": stable_id(source_file, index, page_content),
            "parser": "docling",
            "source": source_file,
            "filename": source_file,
            "source_file": source_file,
            "chunk_index": index,
            "content_type": "image",
            "page_start": min(pages) if pages else None,
            "page_end": max(pages) if pages else None,
            "bbox": extract_bboxes([picture])[:5],
            "title": None,
            "title_confidence": "missing",
            "table_title": None,
            "image_title": None,
            "image_data_url": image_data_url(image_preview),
            "image_mime_type": image_preview.mime_type,
            "image_extraction_status": image_preview.status,
            "docling_labels": [DocItemLabel.PICTURE.value],
        },
    )


def picture_refs(doc_items) -> set[str]:
    return {picture_ref(item) for item in doc_items if isinstance(item, PictureItem)}


def picture_ref(item: PictureItem) -> str:
    ref = getattr(item, "self_ref", None)
    return str(ref) if ref else str(id(item))
