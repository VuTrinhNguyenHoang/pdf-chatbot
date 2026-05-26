import base64
import hashlib
import io
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from docling.chunking import DocChunk, HybridChunker
from docling.datamodel.base_models import DocItemLabel, InputFormat
from docling.datamodel.document import PictureItem, TableItem
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from langchain_core.documents import Document
from openai import OpenAI
from PIL import Image

from src.ingestion_graph.state import IndexSource
from src.shared import settings

VISION_PROMPT = (
    "Describe this image concisely (2-4 sentences). Include: what the image shows, "
    "any visible text, numbers, or labels, and the insight it provides in a document "
    "context (e.g. trend of a chart, structure of a diagram, subject of a photo)."
)


@dataclass(frozen=True)
class ImagePreview:
    data: bytes | None
    mime_type: str | None
    status: str


def parse_sources_with_docling(sources: list[IndexSource]) -> list[Document]:
    converter = _make_document_converter()
    chunker = HybridChunker(repeat_table_header=True)
    vision = OpenAI() if settings.ENABLE_IMAGE_DESCRIPTIONS else None
    image_cache: dict[str, str] = {}

    all_docs: list[Document] = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        for source in sources:
            path = _write_source(source, Path(tmp_dir))
            result = converter.convert(str(path))
            dl_doc = result.document
            chunks = list(chunker.chunk(dl_doc))
            seen_tables: set[str] = set()
            seen_pictures: set[str] = set()
            image_budget = {"remaining": settings.MAX_IMAGE_DESCRIPTIONS_PER_FILE}
            for idx, chunk in enumerate(chunks):
                doc_items = list(chunk.meta.doc_items or [])
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
                    if doc.metadata.get("content_type") == "image":
                        seen_pictures.update(_picture_refs(doc_items))

            if not settings.ENABLE_IMAGE_EXTRACTION:
                continue

            for picture_idx, picture in enumerate(getattr(dl_doc, "pictures", [])):
                if _picture_ref(picture) in seen_pictures:
                    continue
                all_docs.append(
                    _picture_to_document(
                        picture,
                        len(chunks) + picture_idx,
                        source["filename"],
                        dl_doc,
                        vision,
                        image_cache,
                        image_budget,
                    )
                )

    return all_docs


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_document_converter() -> DocumentConverter:
    options = PdfPipelineOptions()
    options.generate_picture_images = settings.ENABLE_IMAGE_EXTRACTION
    options.images_scale = settings.PDF_IMAGE_SCALE
    options.do_ocr = settings.DOCLING_OCR
    options.do_table_structure = settings.DOCLING_TABLE_STRUCTURE
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)},
    )


def _write_source(source: IndexSource, tmp_dir: Path) -> Path:
    filename = Path(source["filename"]).name
    path = tmp_dir / filename
    path.write_bytes(base64.b64decode(source["contentBase64"]))
    return path


def _picture_refs(doc_items) -> set[str]:
    return {_picture_ref(item) for item in doc_items if isinstance(item, PictureItem)}


def _picture_ref(item: PictureItem) -> str:
    ref = getattr(item, "self_ref", None)
    return str(ref) if ref else str(id(item))


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

    if content_type == "image" and not settings.ENABLE_IMAGE_EXTRACTION:
        return None

    image_preview = (
        _extract_image_preview(doc_items, dl_doc) if content_type == "image" else None
    )

    if content_type == "image":
        page_content = _describe_image(
            image_preview,
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
        "image_data_url": _image_data_url(image_preview),
        "image_mime_type": image_preview.mime_type if image_preview else None,
        "image_extraction_status": image_preview.status if image_preview else None,
        "docling_labels": sorted(l.value for l in labels),
    }
    return Document(page_content=page_content, metadata=metadata)


def _picture_to_document(
    picture: PictureItem,
    index: int,
    filename: str,
    dl_doc,
    vision: OpenAI | None,
    image_cache: dict[str, str],
    image_budget: dict[str, int],
) -> Document:
    source_file = Path(filename).name
    image_preview = _extract_image_preview([picture], dl_doc)
    page_content = _describe_image(image_preview, vision, "", image_cache, image_budget)
    pages = _extract_pages([picture])

    return Document(
        page_content=page_content,
        metadata={
            "uuid": _stable_id(source_file, index, page_content),
            "parser": "docling",
            "source": source_file,
            "filename": source_file,
            "source_file": source_file,
            "chunk_index": index,
            "content_type": "image",
            "page_start": min(pages) if pages else None,
            "page_end": max(pages) if pages else None,
            "bbox": _extract_bboxes([picture])[:5],
            "title": None,
            "title_confidence": "missing",
            "table_title": None,
            "image_title": None,
            "image_data_url": _image_data_url(image_preview),
            "image_mime_type": image_preview.mime_type,
            "image_extraction_status": image_preview.status,
            "docling_labels": [DocItemLabel.PICTURE.value],
        },
    )


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


def _extract_image_preview(doc_items, dl_doc) -> ImagePreview:
    for item in doc_items:
        if not isinstance(item, PictureItem):
            continue
        try:
            pil_img = item.get_image(dl_doc)
            if pil_img is None:
                continue
            encoded = _encode_image_preview(pil_img)
            if len(encoded) > settings.MAX_IMAGE_PREVIEW_BYTES:
                return ImagePreview(None, None, "too_large")
            return ImagePreview(encoded, "image/jpeg", "extracted")
        except Exception:
            pass
    return ImagePreview(None, None, "missing")


def _encode_image_preview(pil_img) -> bytes:
    image = pil_img.copy()
    image.thumbnail((settings.PDF_IMAGE_MAX_EDGE, settings.PDF_IMAGE_MAX_EDGE))
    if image.mode in {"RGBA", "LA"}:
        bg = Image.new("RGB", image.size, "white")
        bg.paste(image, mask=image.getchannel("A"))
        image = bg
    elif image.mode != "RGB":
        image = image.convert("RGB")

    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue()


def _describe_image(
    image_preview: ImagePreview | None,
    vision: OpenAI | None,
    fallback: str,
    image_cache: dict[str, str],
    image_budget: dict[str, int],
) -> str:
    if vision is None or image_preview is None or image_preview.data is None:
        return _image_fallback(fallback)

    try:
        image_hash = hashlib.sha1(image_preview.data).hexdigest()
        if image_hash in image_cache:
            return image_cache[image_hash]
        if image_budget["remaining"] <= 0:
            return _image_fallback(fallback)

        image_budget["remaining"] -= 1
        b64 = base64.b64encode(image_preview.data).decode()
        resp = vision.chat.completions.create(
            model=settings.VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image_preview.mime_type};base64,{b64}",
                        },
                    },
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


def _image_data_url(image_preview: ImagePreview | None) -> str | None:
    if (
        image_preview is None
        or image_preview.data is None
        or image_preview.mime_type is None
    ):
        return None
    b64 = base64.b64encode(image_preview.data).decode()
    return f"data:{image_preview.mime_type};base64,{b64}"


def _image_fallback(fallback: str) -> str:
    return fallback or "Image extracted from the document."


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
