"""Thread-safe, process-safe JSON registry for RAG versions."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterator


class RagRegistryError(Exception):
    """Base exception for registry operations."""


class UnknownVersionError(RagRegistryError):
    """Raised when an operation refers to an unregistered version."""


class EmptyHistoryError(RagRegistryError):
    """Raised when rollback is requested without prior activations."""


def _registry_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path).expanduser()
    configured_path = os.getenv("RAG_REGISTRY_PATH")
    if configured_path:
        return Path(configured_path).expanduser()
    return Path(__file__).resolve().parents[2] / "data" / "rag_registry.json"


@contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_file:
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0)
            if lock_file.read(1) == b"":
                lock_file.seek(0)
                lock_file.write(b"0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _empty_registry() -> dict[str, Any]:
    return {"active": None, "history": [], "versions": {}}


def _load_unlocked(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_registry()
    with path.open("r", encoding="utf-8") as registry_file:
        registry = json.load(registry_file)
    if not isinstance(registry, dict) or not {"active", "history", "versions"}.issubset(registry):
        raise RagRegistryError(f"Invalid RAG registry format in {path}")
    return registry


def _save_unlocked(registry: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(registry, temporary_file, indent=2, sort_keys=True)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def load(path: str | Path | None = None) -> dict[str, Any]:
    """Load and return the registry, or an empty registry when absent."""
    registry_path = _registry_path(path)
    with _file_lock(registry_path):
        return _load_unlocked(registry_path)


def save(registry: dict[str, Any], path: str | Path | None = None) -> None:
    """Atomically save a registry snapshot as JSON."""
    registry_path = _registry_path(path)
    with _file_lock(registry_path):
        _save_unlocked(registry, registry_path)


def register_version(
    version_id: str,
    config: Any,
    corpus_hash: str,
    num_docs: int,
    notes: str = "",
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Register a version once and return its immutable registry record."""
    config_data = config.__dict__ if hasattr(config, "__dict__") else dict(config)
    registry_path = _registry_path(path)
    with _file_lock(registry_path):
        registry = _load_unlocked(registry_path)
        if version_id in registry["versions"]:
            record = registry["versions"][version_id]
            if record["config"] != config_data or record["corpus_hash"] != corpus_hash:
                raise RagRegistryError(
                    f"Version ID {version_id} is already registered with different index data"
                )
            return {"version_id": version_id, **record}
        record = {
            "config": config_data,
            "corpus_hash": corpus_hash,
            "num_docs": num_docs,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "notes": notes,
        }
        registry["versions"][version_id] = record
        _save_unlocked(registry, registry_path)
        return {"version_id": version_id, **record}


def activate(version_id: str, path: str | Path | None = None) -> dict[str, Any]:
    """Activate a registered version, saving the previous active ID in history."""
    registry_path = _registry_path(path)
    with _file_lock(registry_path):
        registry = _load_unlocked(registry_path)
        if version_id not in registry["versions"]:
            raise UnknownVersionError(f"Unknown RAG version: {version_id}")
        previous = registry["active"]
        if previous is not None and previous != version_id:
            registry["history"].append(previous)
        registry["active"] = version_id
        _save_unlocked(registry, registry_path)
        return {"version_id": version_id, **registry["versions"][version_id]}


def rollback(path: str | Path | None = None) -> dict[str, Any]:
    """Restore and return the most recently active prior version."""
    registry_path = _registry_path(path)
    with _file_lock(registry_path):
        registry = _load_unlocked(registry_path)
        if not registry["history"]:
            raise EmptyHistoryError("Cannot roll back: RAG activation history is empty")
        version_id = registry["history"].pop()
        if version_id not in registry["versions"]:
            raise UnknownVersionError(f"Unknown RAG version in history: {version_id}")
        registry["active"] = version_id
        _save_unlocked(registry, registry_path)
        return {"version_id": version_id, **registry["versions"][version_id]}


def get_active(path: str | Path | None = None) -> dict[str, Any] | None:
    """Return the active version record, or None when nothing is active."""
    registry = load(path)
    version_id = registry["active"]
    if version_id is None:
        return None
    return get_version(version_id, path)


def list_versions(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Return registered version records ordered newest first."""
    registry = load(path)
    return [
        {"version_id": version_id, **record}
        for version_id, record in sorted(
            registry["versions"].items(),
            key=lambda item: item[1]["created_at"],
            reverse=True,
        )
    ]


def get_version(version_id: str, path: str | Path | None = None) -> dict[str, Any]:
    """Return one registered version record or raise UnknownVersionError."""
    registry = load(path)
    try:
        record = registry["versions"][version_id]
    except KeyError as error:
        raise UnknownVersionError(f"Unknown RAG version: {version_id}") from error
    return {"version_id": version_id, **record}


def remove_versions(
    version_ids: list[str], path: str | Path | None = None
) -> list[str]:
    """Remove requested unprotected versions and return the IDs actually removed."""
    registry_path = _registry_path(path)
    with _file_lock(registry_path):
        registry = _load_unlocked(registry_path)
        protected = set(registry["history"])
        if registry["active"] is not None:
            protected.add(registry["active"])
        removed = []
        for version_id in version_ids:
            if version_id in registry["versions"] and version_id not in protected:
                del registry["versions"][version_id]
                removed.append(version_id)
        if removed:
            _save_unlocked(registry, registry_path)
        return removed