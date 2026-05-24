from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.documents import Document
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from src.shared.state import reduce_docs


class AgentState(TypedDict, total=False):
    query: str
    retrieval_query: str      # current search query; may be rewritten by checkEnough
    route: str
    messages: Annotated[list[AnyMessage], add_messages]
    documents: Annotated[list[Document], reduce_docs]
    iteration_count: int      # number of checkEnough evaluations completed
    is_sufficient: bool       # whether retrieved docs are sufficient to answer
