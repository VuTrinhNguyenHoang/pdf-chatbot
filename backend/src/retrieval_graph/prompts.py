from langchain_core.prompts import ChatPromptTemplate


ROUTER_SYSTEM_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a routing assistant. Your job is to determine if a question "
            "needs document retrieval or can be answered directly.\n\n"
            "Respond with either:\n"
            "'retrieve' - if the question requires retrieving documents\n"
            "'direct' - if the question can be answered directly AND your direct answer",
        ),
        ("human", "{query}"),
    ]
)

RESPONSE_SYSTEM_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an assistant for question-answering tasks. Use the following "
            "pieces of retrieved context to answer the question.\n"
            "If you don't know the answer, just say that you don't know. Use three "
            "sentences maximum and keep the answer concise.\n\n"
            "question:\n"
            "{question}\n\n"
            "context:\n"
            "{context}\n",
        ),
    ]
)
