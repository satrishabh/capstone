"""Configuration values for an indexed RAG version."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RagConfig:
    """Describe index-affecting and query-time RAG settings."""

    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    top_k: int
    reranker: str
    prompt_version: str