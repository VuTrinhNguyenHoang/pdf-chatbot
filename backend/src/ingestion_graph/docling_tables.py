from docling.datamodel.document import TableItem


def extract_table_markdown(doc_items, dl_doc, fallback: str) -> str:
    for item in doc_items:
        if isinstance(item, TableItem):
            try:
                md = item.export_to_markdown(dl_doc)
                if md:
                    return md
            except Exception:
                pass
    return fallback or ""
