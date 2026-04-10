import os
from dataclasses import dataclass

from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from supabase import create_client

from src.shared.configuration import BaseConfiguration, ensure_base_configuration

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


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

        return [
            Document(
                metadata=match.get("metadata", {}),
                page_content=match.get("content", ""),
            )
            for match in response.data
            if match.get("content")
        ]


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
