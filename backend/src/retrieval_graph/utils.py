from langchain_core.documents import Document


def format_doc(doc: Document) -> str:
    metadata = doc.metadata or {}
    content_type = metadata.get("content_type", "text")

    parts = []
    for key in ("source_file", "page_start", "page_end"):
        val = metadata.get(key)
        if val is not None:
            parts.append(f'{key}="{val}"')

    title = (
        metadata.get("table_title")
        or metadata.get("image_title")
        or metadata.get("title")
    )
    if title:
        parts.append(f'title="{title}"')

    attrs = (" " + " ".join(parts)) if parts else ""

    if content_type == "table":
        return f"<table{attrs}>\n{doc.page_content}\n</table>"
    if content_type == "image":
        return f"<image{attrs}>\n{doc.page_content}\n</image>"
    return f"<document{attrs}>\n{doc.page_content}\n</document>"


def format_docs(docs: list[Document] | None = None) -> str:
    if not docs:
        return "<context></context>"
    return "<context>\n" + "\n".join(format_doc(doc) for doc in docs) + "\n</context>"
