from src.shared.configuration import BaseConfiguration, ensure_base_configuration


class AgentConfiguration(BaseConfiguration, total=False):
    queryModel: str
    candidateK: int
    rerank: bool


def ensure_agent_configuration(config) -> AgentConfiguration:
    configurable = dict((config or {}).get("configurable", {}))
    base_config = ensure_base_configuration(config)
    k = int(configurable.get("k") or base_config["k"])
    base_config["k"] = k
    return AgentConfiguration(
        **base_config,
        queryModel=str(configurable.get("queryModel") or "openai/gpt-4o-mini"),
        candidateK=max(k, int(configurable.get("candidateK") or k)),
        rerank=_as_bool(configurable.get("rerank")),
    )


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
