import base64
import tempfile
from pathlib import Path

from docling.chunking import HybridChunker
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from langchain_core.documents import Document
from openai import OpenAI

from src.ingestion_graph.docling_documents import (
    chunk_to_document,
    picture_ref,
    picture_refs,
    picture_to_document,
)
from src.ingestion_graph.state import IndexSource
from src.shared import settings


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
                doc = chunk_to_document(
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
                        seen_pictures.update(picture_refs(doc_items))

            if not settings.ENABLE_IMAGE_EXTRACTION:
                continue

            for picture_idx, picture in enumerate(getattr(dl_doc, "pictures", [])):
                if picture_ref(picture) in seen_pictures:
                    continue
                all_docs.append(
                    picture_to_document(
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
