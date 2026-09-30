"""Retrieve evidence from a selected immutable RAG version."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
from typing import Any

from . import registry


class NoActiveVersionError(registry.RagRegistryError):
    """Raised when retrieval needs an active version but none is configured."""


def _versions_root(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    configured_path = os.getenv("RAG_VECTORSTORE_PATH")
    if configured_path:
        return Path(configured_path).expanduser()
    return Path(__file__).resolve().parents[2] / "vectorstore" / "rag_versions"


def _make_embeddings(model_name: str) -> Any:
    from rag import EMBEDDING_MODEL, GoogleGenerativeAIEmbeddings, get_embeddings

    if model_name == EMBEDDING_MODEL:
        return get_embeddings()
    return GoogleGenerativeAIEmbeddings(model=model_name)


def _load_rag_components() -> tuple[Any, Any, Any]:
    from langchain_community.vectorstores import FAISS
    from rag import BM25Retriever, HybridReranker

    return FAISS, BM25Retriever, HybridReranker


def retrieve(
    query: str,
    version_id: str | None = None,
    *,
    registry_path: str | Path | None = None,
    vectorstore_root: str | Path | None = None,
) -> dict[str, Any]:
    """Retrieve top-ranked chunks and provenance from a versioned FAISS index."""
    if version_id is None:
        active = registry.get_active(registry_path)
        if active is None:
            raise NoActiveVersionError("No active RAG version is configured")
        version_id = active["version_id"]
    version = registry.get_version(version_id, registry_path)
    config = version["config"]
    embedding_model = config["embedding_model"]
    embeddings = _make_embeddings(embedding_model)
    faiss_class, bm25_retriever_class, hybrid_reranker_class = _load_rag_components()
    index_path = _versions_root(vectorstore_root) / version_id
    vectorstore = faiss_class.load_local(
        str(index_path),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    top_k = int(config["top_k"])
    reranker = (config.get("reranker") or "none").lower()
    candidates = max(top_k * 2, top_k) if reranker == "hybrid" else top_k
    vector_results = vectorstore.similarity_search_with_score(query, k=candidates)

    if reranker == "hybrid":
        all_documents = list(vectorstore.docstore._dict.values())
        bm25_results = bm25_retriever_class(all_documents).retrieve(query, k=candidates)
        reranked = hybrid_reranker_class().rerank(
            bm25_results,
            [
                {
                    "content": doc.page_content,
                    "source": doc.metadata.get("source", "unknown"),
                    "score": float(score),
                }
                for doc, score in vector_results
            ],
            k=top_k,
        )
        chunks = [item["content"] for item in reranked]
        docs_by_content = {doc.page_content: doc for doc in all_documents}
        doc_ids = [
            str(
                docs_by_content[item["content"]].metadata.get("doc_id")
                or item["source"]
            )
            for item in reranked
        ]
        scores = [float(item["hybrid_score"]) for item in reranked]
    elif reranker in {"none", ""}:
        chunks = [doc.page_content for doc, _ in vector_results]
        doc_ids = [
            str(doc.metadata.get("doc_id") or doc.metadata.get("source", "unknown"))
            for doc, _ in vector_results
        ]
        scores = [float(score) for _, score in vector_results]
    else:
        raise ValueError(f"Unsupported RAG reranker: {reranker}")

    return {
        "version_id": version_id,
        "chunks": chunks,
        "doc_ids": doc_ids,
        "scores": scores,
    }


def pick_version(
    user_id: str,
    canary_id: str,
    canary_percent: float,
    *,
    registry_path: str | Path | None = None,
) -> str:
    """Choose canary or active version deterministically for a user ID."""
    if not 0 <= canary_percent <= 100:
        raise ValueError("canary_percent must be between 0 and 100")
    active = registry.get_active(registry_path)
    if active is None:
        raise NoActiveVersionError("No active RAG version is configured")
    registry.get_version(canary_id, registry_path)
    bucket = int(sha256(user_id.encode("utf-8")).hexdigest()[:8], 16) % 10_000
    return canary_id if bucket < canary_percent * 100 else active["version_id"]