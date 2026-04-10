from langchain_core.documents import Document


def format_doc(doc: Document) -> str:
    metadata = doc.metadata or {}
    meta = "".join(f" {key}={value}" for key, value in metadata.items())
    meta_str = f" {meta}" if meta else ""
    return f"<document{meta_str}>\n{doc.page_content}\n</document>"


def format_docs(docs: list[Document] | None = None) -> str:
    if not docs:
        return "<documents></documents>"
    formatted = "\n".join(format_doc(doc) for doc in docs)
    return f"<documents>\n{formatted}\n</documents>"
