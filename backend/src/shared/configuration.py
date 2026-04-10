from typing import Any, Literal, TypedDict

from langchain_core.runnables import RunnableConfig


class BaseConfiguration(TypedDict, total=False):
    retrieverProvider: Literal["supabase"]
    filterKwargs: dict[str, Any]
    k: int


def ensure_base_configuration(
    config: RunnableConfig | None,
) -> BaseConfiguration:
    configurable = dict((config or {}).get("configurable", {}))
    return BaseConfiguration(
        retrieverProvider=str(configurable.get("retrieverProvider") or "supabase"),
        filterKwargs=dict(configurable.get("filterKwargs") or {}),
        k=int(configurable.get("k") or 5),
    )
