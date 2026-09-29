"""Cortex AI wrapper with LangSmith tracing support."""
import json
import os
import time
from snowflake_utils import get_connection

CORTEX_MODEL = "llama3.1-8b"

# LangSmith tracing — auto-enabled when LANGCHAIN_TRACING_V2=true
_tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"

try:
    if _tracing_enabled:
        from langsmith import traceable
    else:
        def traceable(*args, **kwargs):
            def decorator(fn):
                return fn
            if args and callable(args[0]):
                return args[0]
            return decorator
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(fn):
            return fn
        if args and callable(args[0]):
            return args[0]
        return decorator


@traceable(run_type="llm", name="cortex_complete")
def cortex_complete(prompt: str, model: str = CORTEX_MODEL) -> str:
    start = time.time()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s) AS response",
            (model, prompt),
        )
        row = cur.fetchone()
        result = row[0] if row else ""
        elapsed = time.time() - start
        print(f"  [Cortex COMPLETE] model={model}, prompt_len={len(prompt)}, response_len={len(result)}, time={elapsed:.1f}s")
        return result
    finally:
        conn.close()


@traceable(run_type="embedding", name="cortex_embed")
def cortex_embed(text: str) -> list[float]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT SNOWFLAKE.CORTEX.EMBED_TEXT_768('e5-base-v2', %s)::VARIANT::ARRAY AS emb",
            (text,),
        )
        row = cur.fetchone()
        if row and row[0]:
            raw = row[0]
            if isinstance(raw, str):
                parsed = json.loads(raw)
                return parsed[0] if isinstance(parsed[0], list) else parsed
            return raw
        return []
    finally:
        conn.close()


def is_tracing_enabled():
    return _tracing_enabled
