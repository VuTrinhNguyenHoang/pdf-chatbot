from typing import Any, Literal
from typing_extensions import TypedDict

from langchain_core.runnables import RunnableConfig

from src.shared import settings


class BaseConfiguration(TypedDict, total=False):
    retrieverProvider: Literal["supabase"]
    filterKwargs: dict[str, Any]
    k: int


def ensure_base_configuration(
    config: RunnableConfig | None,
) -> BaseConfiguration:
    configurable = dict((config or {}).get("configurable", {}))
    return BaseConfiguration(
        retrieverProvider=str(
            configurable.get("retrieverProvider") or settings.RETRIEVER_PROVIDER
        ),
        filterKwargs=dict(configurable.get("filterKwargs") or {}),
        k=int(configurable.get("k") or settings.RETRIEVAL_K),
    )
