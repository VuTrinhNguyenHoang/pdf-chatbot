from typing import Literal

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from src.retrieval_graph.configuration import ensure_agent_configuration
from src.retrieval_graph.prompts import (
    RESPONSE_SYSTEM_PROMPT,
    ROUTER_SYSTEM_PROMPT,
)
from src.retrieval_graph.state import AgentState
from src.retrieval_graph.utils import format_docs
from src.shared.retrieval import make_retriever
from src.shared.utils import load_chat_model


class RouterDecision(BaseModel):
    route: Literal["retrieve", "direct"]
    directAnswer: str | None = None


def check_query_type(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, Literal["retrieve", "direct"]]:
    configuration = ensure_agent_configuration(config)
    model = load_chat_model(configuration["queryModel"])
    formatted_prompt = ROUTER_SYSTEM_PROMPT.invoke({"query": state["query"]})
    response = model.with_structured_output(RouterDecision).invoke(
        formatted_prompt.to_string()
    )
    return {"route": response.route}


def answer_query_directly(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, list]:
    configuration = ensure_agent_configuration(config)
    model = load_chat_model(configuration["queryModel"])
    user_human_message = HumanMessage(content=state["query"])
    response = model.invoke([user_human_message])
    return {"messages": [user_human_message, response]}


def route_query(state: AgentState) -> str:
    route = state.get("route")
    if not route:
        raise ValueError("Route is not set")
    if route == "retrieve":
        return "retrieveDocuments"
    if route == "direct":
        return "directAnswer"
    raise ValueError("Invalid route")


def retrieve_documents(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, list]:
    retriever = make_retriever(config)
    response = retriever.invoke(state["query"])
    return {"documents": response}


def generate_response(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, list]:
    configuration = ensure_agent_configuration(config)
    context = format_docs(state.get("documents"))
    model = load_chat_model(configuration["queryModel"])
    prompt_template = RESPONSE_SYSTEM_PROMPT

    formatted_prompt = prompt_template.invoke(
        {"question": state["query"], "context": context}
    )

    user_human_message = HumanMessage(content=state["query"])
    formatted_prompt_message = HumanMessage(content=formatted_prompt.to_string())

    message_history = [*state.get("messages", []), formatted_prompt_message]
    response = model.invoke(message_history)

    return {"messages": [user_human_message, response]}


builder = StateGraph(AgentState)
builder.add_node("retrieveDocuments", retrieve_documents)
builder.add_node("generateResponse", generate_response)
builder.add_node("checkQueryType", check_query_type)
builder.add_node("directAnswer", answer_query_directly)
builder.add_edge(START, "checkQueryType")
builder.add_conditional_edges(
    "checkQueryType",
    route_query,
    ["retrieveDocuments", "directAnswer"],
)
builder.add_edge("retrieveDocuments", "generateResponse")
builder.add_edge("generateResponse", END)
builder.add_edge("directAnswer", END)

graph = builder.compile().with_config({"run_name": "RetrievalGraph"})
