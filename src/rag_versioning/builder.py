"""Build immutable, version-scoped FAISS indexes."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
from typing import Any, Callable, Iterable

from .config import RagConfig
from . import registry


def corpus_hash(docs: Iterable[Any]) -> str:
    """Hash sorted document identifiers and full text content."""
    rows = []
    for index, doc in enumerate(docs):
        content = getattr(doc, "page_content", None)
        metadata = getattr(doc, "metadata", {})
        if content is None and isinstance(doc, dict):
            content = doc.get("page_content", doc.get("text", ""))
            metadata = doc.get("metadata", doc)
        metadata = metadata or {}
        doc_id = metadata.get("doc_id") or metadata.get("id") or metadata.get("source")
        rows.append((str(doc_id if doc_id is not None else index), str(content or "")))
    canonical = json.dumps(sorted(rows), ensure_ascii=False, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def make_version_id(cfg: RagConfig, corpus_hash_value: str) -> str:
    """Create a deterministic ID from index-affecting settings and corpus hash."""
    index_config = {
        "embedding_model": cfg.embedding_model,
        "chunk_size": cfg.chunk_size,
        "chunk_overlap": cfg.chunk_overlap,
        "corpus_hash": corpus_hash_value,
    }
    canonical = json.dumps(index_config, sort_keys=True, separators=(",", ":"))
    return f"rag-{sha256(canonical.encode('utf-8')).hexdigest()[:10]}"


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


def _load_faiss() -> Any:
    from langchain_community.vectorstores import FAISS

    return FAISS


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    from rag import split_text

    return split_text(text, chunk_size, chunk_overlap)


def build_version(
    docs: Iterable[Any],
    cfg: RagConfig,
    notes: str = "",
    *,
    embedding_factory: Callable[[str], Any] | None = None,
    splitter: Callable[[str, int, int], list[str]] | None = None,
    vectorstore_root: str | Path | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build and register an immutable FAISS index, or return an existing version."""
    documents = list(docs)
    if not documents:
        raise ValueError("Cannot build a RAG version from an empty corpus")
    digest = corpus_hash(documents)
    version_id = make_version_id(cfg, digest)
    try:
        return registry.get_version(version_id, registry_path)
    except registry.UnknownVersionError:
        pass

    chunks = []
    for index, doc in enumerate(documents):
        content = getattr(doc, "page_content", None)
        metadata = getattr(doc, "metadata", {})
        if content is None and isinstance(doc, dict):
            content = doc.get("page_content", doc.get("text", ""))
            metadata = doc.get("metadata", doc)
        metadata = dict(metadata or {})
        doc_id = metadata.get("doc_id") or metadata.get("id") or metadata.get("source")
        metadata["doc_id"] = str(doc_id if doc_id is not None else index)
        chunker = splitter or _split_text
        for chunk_text in chunker(str(content or ""), cfg.chunk_size, cfg.chunk_overlap):
            chunks.append(type(doc)(page_content=chunk_text, metadata=metadata))

    destination = _versions_root(vectorstore_root) / version_id
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(exist_ok=False)
    try:
        embedding_function = embedding_factory or _make_embeddings
        vectorstore = _load_faiss().from_documents(
            documents=chunks,
            embedding=embedding_function(cfg.embedding_model),
        )
        vectorstore.save_local(str(destination))
        return registry.register_version(
            version_id,
            cfg,
            digest,
            len(documents),
            notes=notes,
            path=registry_path,
        )
    except Exception:
        if version_id not in registry.load(registry_path)["versions"]:
            shutil.rmtree(destination, ignore_errors=True)
        raise