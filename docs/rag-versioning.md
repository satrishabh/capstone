# RAG Versioning

This page describes `src/rag_versioning/` and its integration with the existing
helpers in `src/rag.py`.

## Version Identity

Each version identifies an immutable FAISS index. The ID is `rag-` followed by
the first 10 hexadecimal characters of a SHA-256 hash over the index settings and
corpus hash. The corpus hash uses document IDs and full text in a canonical sorted
representation.

| Config field | Changes the index ID? | Meaning |
| --- | --- | --- |
| `embedding_model` | Yes | Model used to embed index chunks and queries. |
| `chunk_size` | Yes | Chunking target passed to the existing splitter. |
| `chunk_overlap` | Yes | Approximate overlap passed to the existing splitter. |
| Corpus document IDs and text | Yes | Identifies the source corpus content. |
| `top_k` | No | Number of results requested at retrieval time. |
| `reranker` | No | Query-time mode: `none` or `hybrid`. |
| `prompt_version` | No | Prompt version label recorded in the config. |

Changing only query-time fields keeps the index ID unchanged. The current workflow
does not dynamically choose diagnostic or planning prompts by `prompt_version`.

## Registry and Index Storage

The JSON registry defaults to `data/rag_registry.json`; set `RAG_REGISTRY_PATH` to
override it. Indexes default to `vectorstore/rag_versions/<version_id>`; set
`RAG_VECTORSTORE_PATH` to override their root. Registry writes are protected by a
lock file and use a temporary file followed by atomic replacement.

Activation sets the active version and pushes the previous active ID onto history.
Rollback pops the most recent history entry and makes it active. Garbage collection
never deletes the active version or an ID in rollback history.

## CLI Workflow

Run the commands with `src` as the working directory:

```powershell
Set-Location .\src
python -m rag_versioning.cli build --notes "baseline"
python -m rag_versioning.cli list
python -m rag_versioning.cli eval rag-<version-id> --eval-set ..\data\rag_eval.json
python -m rag_versioning.cli eval rag-<older-id> --against rag-<newer-id> --eval-set ..\data\rag_eval.json
python -m rag_versioning.cli activate rag-<version-id>
python -m rag_versioning.cli rollback
python -m rag_versioning.cli gc --keep 3
```

Build options include `--embedding-model`, `--chunk-size`, `--chunk-overlap`,
`--top-k`, `--reranker`, `--prompt-version`, and `--notes`. The evaluation JSON
array contains `question` and `expected_doc_id` strings. Evaluation reports hit rate
and mean reciprocal rank (MRR). `gc --keep N` retains the newest N unprotected
versions in addition to all active/history-protected versions.

## Retrieval and Provenance

`retrieve(query, version_id=None)` uses the active version if no ID is supplied.
It returns `version_id`, `chunks`, `doc_ids`, and `scores`. The workflow's RAG node
stores `rag_version` and `rag_doc_ids` in state and emits them in an audit message
and a structured JSON log. Before a version has been activated, the workflow falls
back to legacy retrieval and labels the version `legacy-unversioned`.

`pick_version(user_id, canary_id, canary_percent)` deterministically chooses the
active or canary ID for a user. It is currently a helper only; `rag_agent` does not
use it, so workflow queries currently use the active version. This repository does
not configure LangSmith or Langfuse tracing.

## Implementation Files

- `src/rag_versioning/config.py`: frozen `RagConfig`.
- `src/rag_versioning/registry.py`: JSON registry, activation, rollback, and GC support.
- `src/rag_versioning/builder.py`: corpus hash, deterministic ID, and FAISS build.
- `src/rag_versioning/retriever.py`: retrieval and canary assignment.
- `src/rag_versioning/eval.py`: hit-rate and MRR evaluation.
- `src/rag_versioning/cli.py`: version management CLI.
- `data/rag_eval.json`: sample evaluation set.