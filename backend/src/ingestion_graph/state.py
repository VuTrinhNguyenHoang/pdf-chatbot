from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.documents import Document

from src.shared.state import reduce_docs


class IndexSource(TypedDict):
    filename: str
    mimeType: str
    contentBase64: str


class IndexState(TypedDict, total=False):
    sources: list[IndexSource]
    docs: Annotated[list[Document], reduce_docs]
