from langchain_core.prompts import ChatPromptTemplate


ROUTER_SYSTEM_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a routing assistant. Decide whether a question needs document retrieval.\n\n"
            "Route to 'direct' for:\n"
            "- Greetings, small talk, personal questions (name, job, feelings)\n"
            "- General knowledge answerable without specific documents\n"
            "- Conversational follow-ups that don't require document lookup\n\n"
            "Route to 'retrieve' for:\n"
            "- Questions about specific facts, data, numbers, or events in documents\n"
            "- Questions explicitly about uploaded PDFs or their content\n"
            "- Research questions requiring document evidence\n\n"
            "When in doubt about conversational intent, prefer 'direct'.",
        ),
        ("human", "{query}"),
    ]
)

CHECK_ENOUGH_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are evaluating whether retrieved documents have enough information "
            "to fully answer a user's question.\n\n"
            "Analyze the question and the retrieved context. Decide:\n"
            "1. Are the documents sufficient to give a complete, accurate answer?\n"
            "2. If not sufficient, provide a more specific or alternative search query "
            "that would surface better or additional information.\n\n"
            "Consider:\n"
            "- Do the documents directly address the question?\n"
            "- Is key information missing (specific numbers, comparisons, details)?\n"
            "- Would rephrasing the query find relevant tables, images, or text chunks?\n\n"
            "Question: {query}\n\n"
            "Retrieved Documents:\n{documents}",
        ),
    ]
)

RESPONSE_SYSTEM_PROMPT = (
    "You are an assistant for question-answering tasks. "
    "Use the retrieved context below to answer the user's question.\n\n"
    "The context may contain:\n"
    "- <document>: plain text passages\n"
    "- <table>: tabular data in markdown — reference as a table and quote values precisely\n"
    "- <image>: image descriptions — reference as a figure or visual\n\n"
    "If the context does not contain enough information, say so honestly. "
    "Keep the answer concise and accurate.\n\n"
    "Context:\n{context}"
)
