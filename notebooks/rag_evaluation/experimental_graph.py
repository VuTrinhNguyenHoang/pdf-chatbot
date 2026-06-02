from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from experimental_prompts import RESPONSE_SYSTEM_PROMPT
from experimental_retrieval import make_eval_retriever
from experimental_state import ExperimentalAgentState
from src.retrieval_graph.configuration import ensure_agent_configuration
from src.retrieval_graph.utils import format_docs
from src.shared.utils import load_chat_model


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "did",
    "do",
    "does",
    "for",
    "from",
    "have",
    "how",
    "i",
    "in",
    "is",
    "it",
    "kind",
    "many",
    "of",
    "on",
    "or",
    "the",
    "their",
    "them",
    "there",
    "these",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
}

WHY_SUPPORT_MARKERS = (
    "because",
    "reason",
    "reasons",
    "due to",
    "chosen",
    "selected",
    "so that",
    "in order to",
)


def _normalize_tokens(text: str) -> list[str]:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in text)
    return [token for token in normalized.split() if token]


def _salient_tokens(text: str) -> list[str]:
    return [token for token in _normalize_tokens(text) if token not in STOPWORDS]


def _score_document(query: str, content: str) -> tuple[int, int]:
    query_tokens = _salient_tokens(query)
    content_tokens = _normalize_tokens(content)
    if not query_tokens or not content_tokens:
        return (0, 0)

    content_token_set = set(content_tokens)
    overlap = sum(1 for token in query_tokens if token in content_token_set)
    exact_phrase_bonus = 1 if query.lower() in content.lower() else 0
    return (overlap, exact_phrase_bonus)


def rerank_documents(query: str, documents: list, k: int) -> list:
    scored = []
    for index, document in enumerate(documents):
        overlap, exact_phrase_bonus = _score_document(query, document.page_content)
        scored.append((overlap, exact_phrase_bonus, -index, document))

    scored.sort(reverse=True)
    return [document for _, _, _, document in scored[:k]]


def compute_support_score(query: str, documents: list) -> float:
    query_tokens = _salient_tokens(query)
    if not query_tokens or not documents:
        return 0.0

    top_documents = documents[: min(3, len(documents))]
    content = " ".join(document.page_content for document in top_documents)
    content_tokens = set(_normalize_tokens(content))
    matched = sum(1 for token in query_tokens if token in content_tokens)
    return matched / len(query_tokens)


def _has_rare_entity_match(query: str, documents: list) -> bool:
    query_tokens = _salient_tokens(query)
    if not query_tokens or not documents:
        return False

    content = " ".join(
        document.page_content for document in documents[: min(3, len(documents))]
    )
    content_tokens = set(_normalize_tokens(content))
    rare_tokens = [
        token
        for token in query_tokens
        if any(char.isdigit() for char in token) or len(token) >= 6
    ]
    if not rare_tokens:
        return True
    return any(token in content_tokens for token in rare_tokens)


def _has_why_support(query: str, documents: list) -> bool:
    if not query.strip().lower().startswith("why "):
        return True
    content = " ".join(
        document.page_content.lower() for document in documents[: min(3, len(documents))]
    )
    return any(marker in content for marker in WHY_SUPPORT_MARKERS)


def has_sufficient_support(query: str, documents: list, support_score: float) -> bool:
    query_tokens = _salient_tokens(query)
    if not documents or not query_tokens:
        return False

    if not _has_rare_entity_match(query, documents):
        return False

    if not _has_why_support(query, documents):
        return False

    if support_score >= 0.6:
        return True

    if len(query_tokens) <= 2 and support_score >= 0.5:
        return True

    return False


def retrieve_documents(
    state: ExperimentalAgentState,
    config: RunnableConfig,
) -> dict[str, list | float | bool]:
    configuration = ensure_agent_configuration(config)
    candidate_k = int(
        dict((config or {}).get("configurable", {})).get(
            "candidateK", max(configuration["k"], 8) * 2
        )
    )
    retriever = make_eval_retriever(
        k=configuration["k"],
        candidate_k=candidate_k,
        filter_kwargs=configuration["filterKwargs"],
    )
    candidates = retriever.invoke(state["query"], limit=retriever.candidate_k)
    reranked = rerank_documents(state["query"], candidates, retriever.k)
    support_score = compute_support_score(state["query"], reranked)
    return {
        "documents": reranked,
        "supportScore": support_score,
        "hasSufficientSupport": has_sufficient_support(
            state["query"], reranked, support_score
        ),
    }


def generate_response(
    state: ExperimentalAgentState,
    config: RunnableConfig,
) -> dict[str, list]:
    user_human_message = HumanMessage(content=state["query"])
    if not state.get("hasSufficientSupport", False):
        return {
            "messages": [
                user_human_message,
                AIMessage(content="I don't know based on the provided documents."),
            ]
        }

    configuration = ensure_agent_configuration(config)
    context = format_docs(state.get("documents"))
    model = load_chat_model(configuration["queryModel"])
    formatted_prompt = RESPONSE_SYSTEM_PROMPT.invoke(
        {"question": state["query"], "context": context}
    )
    response = model.invoke(formatted_prompt.to_messages())
    return {"messages": [user_human_message, response]}


builder = StateGraph(ExperimentalAgentState)
builder.add_node("retrieveDocuments", retrieve_documents)
builder.add_node("generateResponse", generate_response)
builder.add_edge(START, "retrieveDocuments")
builder.add_edge("retrieveDocuments", "generateResponse")
builder.add_edge("generateResponse", END)

graph = builder.compile().with_config({"run_name": "ExperimentalRetrievalGraph"})
