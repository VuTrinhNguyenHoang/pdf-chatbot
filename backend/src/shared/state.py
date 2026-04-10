from typing import Any
from uuid import uuid4

from langchain_core.documents import Document


def _ensure_metadata_uuid(metadata: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(metadata)
    normalized["uuid"] = normalized.get("uuid") or str(uuid4())
    return normalized


def _coerce_document(item: Any) -> Document:
    if isinstance(item, Document):
        item.metadata = _ensure_metadata_uuid(item.metadata or {})
        return item

    if isinstance(item, str):
        return Document(
            page_content=item,
            metadata={"uuid": str(uuid4())},
        )

    if isinstance(item, dict):
        if "page_content" in item or "pageContent" in item:
            page_content = item.get("page_content", item.get("pageContent", ""))
            metadata = _ensure_metadata_uuid(dict(item.get("metadata", {})))
            return Document(page_content=page_content, metadata=metadata)

        metadata = _ensure_metadata_uuid(dict(item))
        return Document(page_content="", metadata=metadata)

    raise TypeError(f"Unsupported document type: {type(item)!r}")


def reduce_docs(existing: list[Document] | None, new_docs: Any = None) -> list[Document]:
    if new_docs == "delete":
        return []

    existing_list = list(existing or [])
    existing_ids = {doc.metadata.get("uuid") for doc in existing_list if doc.metadata}

    if isinstance(new_docs, str):
        doc = _coerce_document(new_docs)
        return [*existing_list, doc]

    new_list: list[Document] = []
    if isinstance(new_docs, list):
        for item in new_docs:
            doc = _coerce_document(item)
            doc_id = doc.metadata.get("uuid")
            if doc_id not in existing_ids:
                new_list.append(doc)
                existing_ids.add(doc_id)

    return [*existing_list, *new_list]
