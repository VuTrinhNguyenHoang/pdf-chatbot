from langchain.chat_models import init_chat_model


SUPPORTED_PROVIDERS = (
    "openai",
    "anthropic",
    "azure_openai",
    "cohere",
    "google-vertexai",
    "google-vertexai-web",
    "google-genai",
    "ollama",
    "together",
    "fireworks",
    "mistralai",
    "groq",
    "bedrock",
    "cerebras",
    "deepseek",
    "xai",
)


def load_chat_model(fully_specified_name: str, temperature: float = 0.2):
    index = fully_specified_name.find("/")
    if index == -1:
        if fully_specified_name not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported model: {fully_specified_name}")
        return init_chat_model(fully_specified_name, temperature=temperature)

    provider = fully_specified_name[:index]
    model = fully_specified_name[index + 1 :]
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")

    return init_chat_model(
        model,
        model_provider=provider,
        temperature=temperature,
    )
