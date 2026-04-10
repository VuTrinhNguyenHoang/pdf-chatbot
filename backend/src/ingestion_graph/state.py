from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.documents import Document

from src.shared.state import reduce_docs


class IndexState(TypedDict, total=False):
    docs: Annotated[list[Document], reduce_docs]
