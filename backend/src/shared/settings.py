import os


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int, minimum: int | None = None) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(minimum, parsed) if minimum is not None else parsed


def _float_env(name: str, default: float, minimum: float | None = None) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return max(minimum, parsed) if minimum is not None else parsed


CHAT_MODEL = os.getenv("CHAT_MODEL", "openai/gpt-4o-mini")
VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
MODEL_TEMPERATURE = _float_env("MODEL_TEMPERATURE", 0.2)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

RETRIEVER_PROVIDER = os.getenv("RETRIEVER_PROVIDER", "supabase")
RETRIEVAL_K = _int_env("RETRIEVAL_K", 5, minimum=1)
RETRIEVAL_CANDIDATE_K = _int_env("RETRIEVAL_CANDIDATE_K", 12, minimum=1)
RETRIEVAL_RERANK = _bool_env("RETRIEVAL_RERANK", True)
RETRIEVAL_MAX_ITERATIONS = _int_env("RETRIEVAL_MAX_ITERATIONS", 3, minimum=1)

ENABLE_IMAGE_EXTRACTION = _bool_env("ENABLE_IMAGE_EXTRACTION", True)
ENABLE_IMAGE_DESCRIPTIONS = _bool_env("ENABLE_IMAGE_DESCRIPTIONS", True)
MAX_IMAGE_DESCRIPTIONS_PER_FILE = _int_env(
    "MAX_IMAGE_DESCRIPTIONS_PER_FILE",
    20,
    minimum=0,
)
PDF_IMAGE_SCALE = _float_env("PDF_IMAGE_SCALE", 2.0, minimum=1.0)
PDF_IMAGE_MAX_EDGE = _int_env("PDF_IMAGE_MAX_EDGE", 1400, minimum=320)
MAX_IMAGE_PREVIEW_BYTES = _int_env("MAX_IMAGE_PREVIEW_BYTES", 1_500_000, minimum=0)

DOCLING_OCR = _bool_env("DOCLING_OCR", True)
DOCLING_TABLE_STRUCTURE = _bool_env("DOCLING_TABLE_STRUCTURE", True)
