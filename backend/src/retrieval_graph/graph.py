from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from src.retrieval_graph.configuration import ensure_agent_configuration
from src.retrieval_graph.prompts import (
    CHECK_ENOUGH_PROMPT,
    RESPONSE_SYSTEM_PROMPT,
    ROUTER_SYSTEM_PROMPT,
)
from src.retrieval_graph.rerank import rerank_documents
from src.retrieval_graph.state import AgentState
from src.retrieval_graph.utils import format_docs
from src.shared.retrieval import make_retriever
from src.shared.utils import load_chat_model

MAX_ITERATIONS = 3


class RouterDecision(BaseModel):
    route: Literal["retrieve", "direct"]


class SufficiencyCheck(BaseModel):
    sufficient: bool
    rewritten_query: str | None = None  # provide if not sufficient


def check_query_type(state: AgentState, config: RunnableConfig) -> dict:
    configuration = ensure_agent_configuration(config)
    model = load_chat_model(configuration["queryModel"])
    formatted = ROUTER_SYSTEM_PROMPT.invoke({"query": state["query"]})
    response = model.with_structured_output(RouterDecision).invoke(formatted.to_string())
    return {
        "route": response.route,
        "iteration_count": 0,
        "is_sufficient": False,
        "retrieval_query": "",
        "documents": "delete",
    }


def route_query(state: AgentState) -> str:
    route = state.get("route")
    if route == "retrieve":
        return "retrieveDocuments"
    if route == "direct":
        return "directAnswer"
    raise ValueError(f"Invalid route: {route!r}")


def retrieve_documents(state: AgentState, config: RunnableConfig) -> dict:
    configuration = ensure_agent_configuration(config)
    query = state.get("retrieval_query") or state["query"]
    candidate_k = configuration["candidateK"] if configuration["rerank"] else configuration["k"]
    retriever = make_retriever(_with_retrieval_k(config, candidate_k))
    docs = retriever.invoke(query)

    if not configuration["rerank"]:
        return {"documents": docs[:configuration["k"]]}

    try:
        model = load_chat_model(configuration["queryModel"])
        docs = rerank_documents(state["query"], docs, model, configuration["k"])
    except Exception:
        docs = docs[:configuration["k"]]

    return {"documents": docs}


def _with_retrieval_k(config: RunnableConfig, k: int) -> RunnableConfig:
    configurable = dict((config or {}).get("configurable", {}))
    return {**(config or {}), "configurable": {**configurable, "k": k}}


def check_enough(state: AgentState, config: RunnableConfig) -> dict:
    iteration = state.get("iteration_count", 0) + 1

    # Force proceed after max iterations regardless of sufficiency
    if iteration >= MAX_ITERATIONS:
        return {"iteration_count": iteration, "is_sufficient": True}

    configuration = ensure_agent_configuration(config)
    model = load_chat_model(configuration["queryModel"])

    formatted = CHECK_ENOUGH_PROMPT.invoke({
        "query": state["query"],
        "documents": format_docs(state.get("documents")),
    })
    response = model.with_structured_output(SufficiencyCheck).invoke(formatted.to_string())

    new_query = (
        response.rewritten_query
        if not response.sufficient and response.rewritten_query
        else state.get("retrieval_query") or state["query"]
    )
    return {
        "iteration_count": iteration,
        "is_sufficient": response.sufficient,
        "retrieval_query": new_query,
    }


def route_after_check(state: AgentState) -> str:
    if state.get("is_sufficient"):
        return "generateResponse"
    return "retrieveDocuments"


def generate_response(state: AgentState, config: RunnableConfig) -> dict:
    configuration = ensure_agent_configuration(config)
    model = load_chat_model(configuration["queryModel"])
    context = format_docs(state.get("documents"))

    system_msg = SystemMessage(content=RESPONSE_SYSTEM_PROMPT.format(context=context))
    user_msg = HumanMessage(content=state["query"])
    messages = [system_msg, *state.get("messages", []), user_msg]
    response = model.invoke(messages)
    return {"messages": [user_msg, response]}


def answer_query_directly(state: AgentState, config: RunnableConfig) -> dict:
    configuration = ensure_agent_configuration(config)
    model = load_chat_model(configuration["queryModel"])
    user_msg = HumanMessage(content=state["query"])
    history = [*state.get("messages", []), user_msg]
    response = model.invoke(history)
    return {"messages": [user_msg, response]}


builder = StateGraph(AgentState)
builder.add_node("checkQueryType", check_query_type)
builder.add_node("retrieveDocuments", retrieve_documents)
builder.add_node("checkEnough", check_enough)
builder.add_node("generateResponse", generate_response)
builder.add_node("directAnswer", answer_query_directly)

builder.add_edge(START, "checkQueryType")
builder.add_conditional_edges("checkQueryType", route_query, ["retrieveDocuments", "directAnswer"])
builder.add_edge("retrieveDocuments", "checkEnough")
builder.add_conditional_edges("checkEnough", route_after_check, ["generateResponse", "retrieveDocuments"])
builder.add_edge("generateResponse", END)
builder.add_edge("directAnswer", END)

graph = builder.compile().with_config({"run_name": "RetrievalGraph"})
