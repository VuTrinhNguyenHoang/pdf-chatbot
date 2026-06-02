from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.documents import Document
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from src.shared.state import reduce_docs


class ExperimentalAgentState(TypedDict, total=False):
    query: str
    route: str
    supportScore: float
    hasSufficientSupport: bool
    messages: Annotated[list[AnyMessage], add_messages]
    documents: Annotated[list[Document], reduce_docs]
