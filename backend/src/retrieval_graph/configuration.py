from src.shared.configuration import BaseConfiguration, ensure_base_configuration


class AgentConfiguration(BaseConfiguration, total=False):
    queryModel: str


def ensure_agent_configuration(config) -> AgentConfiguration:
    configurable = dict((config or {}).get("configurable", {}))
    base_config = ensure_base_configuration(config)
    return AgentConfiguration(
        **base_config,
        queryModel=str(configurable.get("queryModel") or "openai/gpt-4o-mini"),
    )
