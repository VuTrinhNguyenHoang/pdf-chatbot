"""This graph exposes an endpoint for uploading docs to be indexed."""

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from src.ingestion_graph.state import IndexState
from src.shared.retrieval import make_retriever
from src.shared.state import reduce_docs

from src.ingestion_graph.docling_parser import parse_sources_with_docling

def parse_documents(
    state: IndexState, 
    config: RunnableConfig | None = None
) -> dict[str, list]:
    sources = state.get("sources", [])
    if not sources:
        raise ValueError("No sources provided.")
    return {"docs": parse_sources_with_docling(sources)}


def ingest_docs(
    state: IndexState,
    config: RunnableConfig | None = None,
) -> dict[str, str]:
    if config is None:
        raise ValueError("Configuration required to run ingest_docs.")

    docs = state.get("docs", [])
    if not docs:
        raise ValueError("No documents provided for ingestion.")

    docs = reduce_docs([], docs)

    retriever = make_retriever(config)
    retriever.add_documents(docs)

    return {"docs": "delete"}


builder = StateGraph(IndexState)
builder.add_node("parseDocuments", parse_documents)
builder.add_node("ingestDocs", ingest_docs)
builder.add_edge(START, "parseDocuments")
builder.add_edge("parseDocuments", "ingestDocs")
builder.add_edge("ingestDocs", END)

graph = builder.compile().with_config({"run_name": "IngestionGraph"})
