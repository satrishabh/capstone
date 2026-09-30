"""Command-line management for versioned RAG indexes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any

from . import registry
from .builder import _versions_root, build_version
from .config import RagConfig
from .eval import compare, hit_rate


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and manage immutable RAG versions")
    commands = parser.add_subparsers(dest="command", required=True)

    build_parser = commands.add_parser("build", help="Build a versioned FAISS index")
    build_parser.add_argument("--docs", type=Path)
    build_parser.add_argument("--embedding-model", default="gemini-embedding-2")
    build_parser.add_argument("--chunk-size", type=int, default=1000)
    build_parser.add_argument("--chunk-overlap", type=int, default=200)
    build_parser.add_argument("--top-k", type=int, default=5)
    build_parser.add_argument("--reranker", choices=("none", "hybrid"), default="hybrid")
    build_parser.add_argument("--prompt-version", default="v1")
    build_parser.add_argument("--notes", default="")

    commands.add_parser("list", help="List registered RAG versions")
    activate_parser = commands.add_parser("activate", help="Activate a version")
    activate_parser.add_argument("version_id")
    commands.add_parser("rollback", help="Restore the previous active version")

    eval_parser = commands.add_parser("eval", help="Evaluate a version")
    eval_parser.add_argument("version_id")
    eval_parser.add_argument("--against")
    eval_parser.add_argument("--eval-set", type=Path, default=_default_eval_path())

    gc_parser = commands.add_parser("gc", help="Delete unprotected old versions")
    gc_parser.add_argument("--keep", type=int, required=True)
    return parser


def _default_eval_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "rag_eval.json"


def _emit(value: Any) -> None:
    print(json.dumps(value, indent=2, default=str))


def _build(args: argparse.Namespace) -> dict[str, Any]:
    from rag import load_documents_from_dir

    docs_path = args.docs or Path(__file__).resolve().parents[2] / "rag_docs"
    documents = load_documents_from_dir(docs_path)
    for document in documents:
        source = Path(document.metadata.get("source", "unknown"))
        try:
            document.metadata["doc_id"] = source.resolve().relative_to(
                docs_path.resolve()
            ).as_posix()
        except ValueError:
            document.metadata["doc_id"] = source.name
    config = RagConfig(
        embedding_model=args.embedding_model,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        top_k=args.top_k,
        reranker=args.reranker,
        prompt_version=args.prompt_version,
    )
    return build_version(documents, config, notes=args.notes)


def _gc(keep: int) -> dict[str, Any]:
    if keep < 0:
        raise ValueError("--keep must be zero or greater")
    versions = registry.list_versions()
    current = registry.load()
    protected = set(current["history"])
    if current["active"] is not None:
        protected.add(current["active"])
    unprotected = [
        version["version_id"]
        for version in versions
        if version["version_id"] not in protected
    ]
    candidates = unprotected[keep:]
    removed = registry.remove_versions(candidates)
    root = _versions_root()
    for version_id in removed:
        index_path = root / version_id
        if index_path.exists():
            shutil.rmtree(index_path)
    return {"removed": removed, "kept": len(versions) - len(removed)}


def main(argv: list[str] | None = None) -> int:
    """Parse a RAG management command, execute it, and print JSON output."""
    args = _parser().parse_args(argv)
    if args.command == "build":
        result = _build(args)
    elif args.command == "list":
        registry_data = registry.load()
        result = {
            "active": registry_data["active"],
            "history": registry_data["history"],
            "versions": registry.list_versions(),
        }
    elif args.command == "activate":
        result = registry.activate(args.version_id)
    elif args.command == "rollback":
        result = registry.rollback()
    elif args.command == "eval":
        result = (
            compare(args.version_id, args.against, args.eval_set)
            if args.against
            else hit_rate(args.version_id, args.eval_set)
        )
    else:
        result = _gc(args.keep)
    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())