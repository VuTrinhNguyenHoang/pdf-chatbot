from langchain_core.prompts import ChatPromptTemplate


RESPONSE_SYSTEM_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You answer questions only from the retrieved document context.\n"
            "Rules:\n"
            "- Use only the provided context.\n"
            "- Do not use outside knowledge.\n"
            "- If the answer is not fully supported by the context, say exactly: "
            "\"I don't know based on the provided documents.\"\n"
            "- When the answer is supported, respond concisely and include only the "
            "information needed to answer the question.\n"
            "- Do not add speculation, background knowledge, or extra examples.\n\n"
            "question:\n"
            "{question}\n\n"
            "context:\n"
            "{context}\n",
        ),
    ]
)
