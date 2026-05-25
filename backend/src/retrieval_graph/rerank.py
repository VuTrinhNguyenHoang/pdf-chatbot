from langchain_core.documents import Document
from pydantic import BaseModel, Field

from src.retrieval_graph.utils import format_doc

RERANK_PROMPT = """You are reranking retrieved PDF chunks for a user's question.
Return the most relevant document indexes in descending relevance.
Prefer chunks that directly answer the question with specific evidence.

Question: {query}

Documents:
{documents}
"""


class RankedDocument(BaseModel):
    index: int = Field(ge=0)


class RerankDecision(BaseModel):
    documents: list[RankedDocument]


def rerank_documents(query: str, docs: list[Document], model, k: int) -> list[Document]:
    if len(docs) <= k:
        return docs[:k]

    indexed_docs = "\n\n".join(
        f"[{idx}]\n{format_doc(doc)}" for idx, doc in enumerate(docs)
    )
    prompt = RERANK_PROMPT.format(query=query, documents=indexed_docs)
    response = model.with_structured_output(RerankDecision).invoke(prompt)

    selected: list[Document] = []
    seen: set[int] = set()
    for item in response.documents:
        if item.index in seen or item.index >= len(docs):
            continue
        selected.append(docs[item.index])
        seen.add(item.index)
        if len(selected) == k:
            return selected

    for idx, doc in enumerate(docs):
        if idx not in seen:
            selected.append(doc)
        if len(selected) == k:
            break

    return selected
