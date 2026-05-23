import os
from dataclasses import dataclass

from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from supabase import create_client

from src.shared.configuration import BaseConfiguration, ensure_base_configuration

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

PUBLIC_METADATA_KEYS = (
    "uuid",
    "source",
    "filename",
    "source_file",
    "content_type",
    "page_start",
    "page_end",
    "title",
    "table_title",
    "image_title",
    "chunk_index",
    "parser",
    "loc",
)

def public_metadata(metadata: dict) -> dict:
    return {
        key: metadata[key]
        for key in PUBLIC_METADATA_KEYS
        if metadata.get(key) is not None
    }

def document_key(document: Document) -> tuple:
    metadata = document.metadata or {}

    if metadata.get("uuid"):
        return ("uuid", metadata["uuid"])

    if metadata.get("source_file") is not None and metadata.get("chunk_index") is not None:
        return ("chunk", metadata.get("source_file"), metadata.get("chunk_index"))

    return ("content", document.page_content)

def deduplicate_documents(documents: list[Document]) -> list[Document]:
    selected: list[Document] = []
    seen_keys: set[tuple] = set()

    for document in documents:
        key = document_key(document)
        if key in seen_keys:
            continue

        selected.append(document)
        seen_keys.add(key)

    return selected

@dataclass
class VectorStoreRetrieverHandle:
    vector_store: SupabaseVectorStore
    k: int
    filter_kwargs: dict

    def add_documents(self, docs: list[Document]) -> list[str]:
        return self.vector_store.add_documents(docs)

    def invoke(self, query: str) -> list[Document]:
        query_embedding = self.vector_store.embeddings.embed_query(query)
        match_documents_params = self.vector_store.match_args(
            query_embedding,
            self.filter_kwargs or None,
        )
        query_builder = self.vector_store._client.rpc(
            self.vector_store.query_name,
            match_documents_params,
        )
        response = query_builder.limit(self.k).execute()

        documents = [
            Document(
                metadata=public_metadata(match.get("metadata", {})),
                page_content=match.get("content", ""),
            )
            for match in response.data
            if match.get("content")
        ]

        return deduplicate_documents(documents)


def load_embeddings() -> OpenAIEmbeddings:
    model_name = os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    return OpenAIEmbeddings(model=model_name)


def make_supabase_retriever(
    configuration: BaseConfiguration,
) -> VectorStoreRetrieverHandle:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        raise ValueError(
            "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables are not defined"
        )

    embeddings = load_embeddings()
    supabase_client = create_client(
        os.environ.get("SUPABASE_URL", ""),
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""),
    )
    vector_store = SupabaseVectorStore(
        client=supabase_client,
        embedding=embeddings,
        table_name="documents",
        query_name="match_documents",
    )
    return VectorStoreRetrieverHandle(
        vector_store=vector_store,
        k=configuration["k"],
        filter_kwargs=configuration["filterKwargs"],
    )


def make_retriever(config) -> VectorStoreRetrieverHandle:
    configuration = ensure_base_configuration(config)
    if configuration["retrieverProvider"] == "supabase":
        return make_supabase_retriever(configuration)
    raise ValueError(
        f"Unsupported retriever provider: {configuration['retrieverProvider']}"
    )
