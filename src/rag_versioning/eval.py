"""Evaluate retrieval quality for one or more RAG versions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .retriever import retrieve


def _load_eval_set(eval_set: str | Path | Iterable[dict[str, str]]) -> list[dict[str, str]]:
    if isinstance(eval_set, (str, Path)):
        with Path(eval_set).open("r", encoding="utf-8") as eval_file:
            records = json.load(eval_file)
    else:
        records = list(eval_set)
    for record in records:
        if not isinstance(record.get("question"), str) or not isinstance(
            record.get("expected_doc_id"), str
        ):
            raise ValueError("Each eval record needs question and expected_doc_id strings")
    return records


def hit_rate(
    version_id: str,
    eval_set: str | Path | Iterable[dict[str, str]],
) -> dict[str, Any]:
    """Return hit rate, mean reciprocal rank, and sample count for a version."""
    records = _load_eval_set(eval_set)
    reciprocal_ranks = []
    hits = 0
    for record in records:
        results = retrieve(record["question"], version_id=version_id)
        try:
            rank = results["doc_ids"].index(record["expected_doc_id"]) + 1
        except ValueError:
            reciprocal_ranks.append(0.0)
        else:
            hits += 1
            reciprocal_ranks.append(1.0 / rank)
    total = len(records)
    return {
        "version_id": version_id,
        "hit_rate": hits / total if total else 0.0,
        "mrr": sum(reciprocal_ranks) / total if total else 0.0,
        "total": total,
    }


def compare(
    version_a: str,
    version_b: str,
    eval_set: str | Path | Iterable[dict[str, str]],
) -> dict[str, Any]:
    """Evaluate two versions on the same records and return metric deltas."""
    records = _load_eval_set(eval_set)
    metrics_a = hit_rate(version_a, records)
    metrics_b = hit_rate(version_b, records)
    return {
        "version_a": metrics_a,
        "version_b": metrics_b,
        "delta": {
            "hit_rate": metrics_b["hit_rate"] - metrics_a["hit_rate"],
            "mrr": metrics_b["mrr"] - metrics_a["mrr"],
        },
    }