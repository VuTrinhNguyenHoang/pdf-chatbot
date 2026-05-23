from langchain_core.documents import Document


def format_doc(doc: Document) -> str:
    metadata = doc.metadata or {}
    allowed = {
        "source_file": metadata.get("source_file"),
        "content_type": metadata.get("content_type"),
        "page_start": metadata.get("page_start"),
        "page_end": metadata.get("page_end"),
        "title": metadata.get("title"),
        "table_title": metadata.get("table_title"),
        "image_title": metadata.get("image_title")
    }
    meta = "".join(
        f" {key}={value}"
        for key, value in allowed.items()
        if value is not None
    )
    return f"<document{meta}>\n{doc.page_content}\n</document>"


def format_docs(docs: list[Document] | None = None) -> str:
    if not docs:
        return "<documents></documents>"
    formatted = "\n".join(format_doc(doc) for doc in docs)
    return f"<documents>\n{formatted}\n</documents>"
