import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_versioning.config import RagConfig
from rag_versioning import registry
from rag_versioning import builder
from rag_versioning import eval as rag_eval
from rag_versioning import retriever
from rag_versioning import cli


def _config() -> RagConfig:
    return RagConfig(
        embedding_model="test-embedding",
        chunk_size=100,
        chunk_overlap=10,
        top_k=3,
        reranker="none",
        prompt_version="v1",
    )


def _register(path: Path, version_id: str) -> None:
    registry.register_version(version_id, _config(), "corpus", 1, path=path)


def test_config_is_frozen() -> None:
    config = _config()
    with pytest.raises(AttributeError):
        config.top_k = 4


def test_activate_and_rollback_restore_previous_version(tmp_path: Path) -> None:
    path = tmp_path / "rag_registry.json"
    _register(path, "rag-one")
    _register(path, "rag-two")

    registry.activate("rag-one", path)
    registry.activate("rag-two", path)

    assert registry.get_active(path)["version_id"] == "rag-two"
    assert registry.rollback(path)["version_id"] == "rag-one"
    assert registry.load(path)["history"] == []


def test_rollback_with_empty_history_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(registry.EmptyHistoryError, match="history is empty"):
        registry.rollback(tmp_path / "rag_registry.json")


def test_interrupted_atomic_write_preserves_previous_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "rag_registry.json"
    original = {"active": None, "history": [], "versions": {}}
    registry.save(original, path)

    def interrupted_replace(_source: Path, _destination: Path) -> None:
        raise OSError("simulated interruption")

    monkeypatch.setattr(registry.os, "replace", interrupted_replace)
    with pytest.raises(OSError, match="simulated interruption"):
        registry.save({"active": "rag-new", "history": [], "versions": {}}, path)

    assert registry.load(path) == original


def test_version_id_is_stable_and_ignores_query_time_settings() -> None:
    docs = [SimpleNamespace(page_content="engine oil", metadata={"doc_id": "oil.md"})]
    digest = builder.corpus_hash(docs)

    original_id = builder.make_version_id(_config(), digest)
    query_config = replace(_config(), top_k=9, reranker="hybrid", prompt_version="v2")

    assert builder.make_version_id(_config(), digest) == original_id
    assert builder.make_version_id(query_config, digest) == original_id


def test_version_id_changes_with_chunk_size_or_corpus_text() -> None:
    docs = [SimpleNamespace(page_content="engine oil", metadata={"doc_id": "oil.md"})]
    digest = builder.corpus_hash(docs)
    original_id = builder.make_version_id(_config(), digest)
    changed_text = [
        SimpleNamespace(page_content="coolant leak", metadata={"doc_id": "oil.md"})
    ]

    assert builder.make_version_id(replace(_config(), chunk_size=101), digest) != original_id
    assert builder.make_version_id(_config(), builder.corpus_hash(changed_text)) != original_id


def test_build_version_uses_injected_offline_components(tmp_path: Path, monkeypatch) -> None:
    docs = [SimpleNamespace(page_content="engine oil pressure", metadata={"doc_id": "oil.md"})]
    saved_paths = []

    class FakeIndex:
        def save_local(self, path: str) -> None:
            saved_paths.append(Path(path))

    class FakeFAISS:
        @staticmethod
        def from_documents(documents, embedding):
            assert embedding == "fake-embedding"
            assert documents
            return FakeIndex()

    monkeypatch.setattr(builder, "_load_faiss", lambda: FakeFAISS)
    path = tmp_path / "registry.json"
    version = builder.build_version(
        docs,
        _config(),
        embedding_factory=lambda _model: "fake-embedding",
        splitter=lambda text, _size, _overlap: text.split(),
        vectorstore_root=tmp_path / "indexes",
        registry_path=path,
    )

    assert saved_paths == [tmp_path / "indexes" / version["version_id"]]
    assert registry.get_version(version["version_id"], path)["num_docs"] == 1


def test_eval_reports_hit_rate_mrr_and_comparison(monkeypatch) -> None:
    def fake_retrieve(question: str, version_id: str) -> dict:
        doc_ids = ["other", "expected"] if version_id == "rag-a" else ["expected"]
        return {"version_id": version_id, "doc_ids": doc_ids, "chunks": [], "scores": []}

    monkeypatch.setattr(rag_eval, "retrieve", fake_retrieve)
    records = [
        {"question": "q1", "expected_doc_id": "expected"},
        {"question": "q2", "expected_doc_id": "missing"},
    ]

    metrics = rag_eval.hit_rate("rag-a", records)
    comparison = rag_eval.compare("rag-a", "rag-b", records)

    assert metrics == {"version_id": "rag-a", "hit_rate": 0.5, "mrr": 0.25, "total": 2}
    assert comparison["delta"] == {"hit_rate": 0.0, "mrr": 0.25}


def test_canary_routing_is_stable_for_user(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    _register(path, "rag-active")
    _register(path, "rag-canary")
    registry.activate("rag-active", path)

    first = retriever.pick_version("user-42", "rag-canary", 50, registry_path=path)
    second = retriever.pick_version("user-42", "rag-canary", 50, registry_path=path)

    assert first == second
    assert first in {"rag-active", "rag-canary"}


def test_retrieve_returns_versioned_chunks_ids_and_scores(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "registry.json"
    version = builder.make_version_id(_config(), "corpus")
    registry.register_version(version, _config(), "corpus", 1, path=path)
    document = SimpleNamespace(
        page_content="oil pressure guidance",
        metadata={"doc_id": "engine_oil_pressure.md"},
    )

    class FakeIndex:
        @staticmethod
        def similarity_search_with_score(_query: str, k: int):
            assert k == _config().top_k
            return [(document, 0.125)]

    class FakeFAISS:
        @staticmethod
        def load_local(_path, _embeddings, allow_dangerous_deserialization):
            assert allow_dangerous_deserialization is True
            return FakeIndex()

    monkeypatch.setattr(retriever, "_make_embeddings", lambda _model: "fake")
    monkeypatch.setattr(retriever, "_load_rag_components", lambda: (FakeFAISS, None, None))

    result = retriever.retrieve(
        "oil pressure", version, registry_path=path, vectorstore_root=tmp_path / "indexes"
    )

    assert result == {
        "version_id": version,
        "chunks": ["oil pressure guidance"],
        "doc_ids": ["engine_oil_pressure.md"],
        "scores": [0.125],
    }


def test_gc_keeps_active_history_and_newest_unprotected(
    tmp_path: Path, monkeypatch
) -> None:
    registry_path = tmp_path / "registry.json"
    index_root = tmp_path / "indexes"
    for version_id in ("rag-one", "rag-two", "rag-three", "rag-four"):
        _register(registry_path, version_id)
        (index_root / version_id).mkdir(parents=True)
    registry.activate("rag-one", registry_path)
    registry.activate("rag-two", registry_path)
    monkeypatch.setenv("RAG_REGISTRY_PATH", str(registry_path))
    monkeypatch.setenv("RAG_VECTORSTORE_PATH", str(index_root))

    result = cli._gc(keep=1)

    assert set(result["removed"]) == {"rag-three"}
    assert not (index_root / "rag-three").exists()
    assert {"rag-one", "rag-two", "rag-four"}.issubset(
        {version["version_id"] for version in registry.list_versions(registry_path)}
    )