"""Cortex AI wrapper — replaces Google Gemini with Snowflake Cortex COMPLETE."""
import json
from snowflake_utils import get_connection

CORTEX_MODEL = "llama3.1-8b"


def cortex_complete(prompt: str, model: str = CORTEX_MODEL) -> str:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s) AS response",
            (model, prompt),
        )
        row = cur.fetchone()
        return row[0] if row else ""
    finally:
        conn.close()


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
