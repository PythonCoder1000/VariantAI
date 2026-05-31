"""Global memory store — durable facts/preferences the AI can update during chats.

A single JSON file holds a flat list of memory items. The AI appends to it by
emitting ``[[MEMORY: ...]]`` directives in its chat replies (parsed in chat.py);
the contents are injected into every chat's system prompt so the assistant
remembers across conversations and variants.

The path is configurable via the ``MEMORY_PATH`` env var (defaults to
``backend/data/memory.json``). Writes are serialized with a lock. NOTE: on an
ephemeral host (e.g. Railway) this file does not survive redeploys — swap for a
durable store (Redis/Postgres) in production.
"""

import json
import os
import threading
import time
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "memory.json"
_lock = threading.Lock()

# Cap to keep the prompt bounded and avoid unbounded growth.
MAX_ITEMS = 50
MAX_ITEM_LEN = 500


def _memory_path() -> Path:
    return Path(os.environ.get("MEMORY_PATH", str(_DEFAULT_PATH)))


def _read_raw() -> list[dict]:
    path = _memory_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        items = data.get("items", []) if isinstance(data, dict) else []
        return items if isinstance(items, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_raw(items: list[dict]) -> None:
    path = _memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"items": items}, indent=2))
    tmp.replace(path)


def load_memory() -> list[dict]:
    """Return all memory items (newest last), each ``{id, text, created_at}``."""
    with _lock:
        return _read_raw()


def add_memories(texts: list[str], *, counter_start: int = 0) -> list[dict]:
    """Append new, de-duplicated memory items. Returns the items actually added.

    ``counter_start`` keeps ids unique within a single batch without relying on
    ``time``-based ids alone (two memories saved in the same call get distinct ids).
    """
    added: list[dict] = []
    with _lock:
        items = _read_raw()
        existing = {i.get("text", "").strip().lower() for i in items}
        ts = time.time()
        for offset, raw in enumerate(texts):
            text = (raw or "").strip()
            if not text:
                continue
            text = text[:MAX_ITEM_LEN]
            if text.lower() in existing:
                continue
            item = {"id": f"{int(ts)}-{counter_start + offset}", "text": text, "created_at": ts}
            items.append(item)
            added.append(item)
            existing.add(text.lower())
        if added:
            # Keep only the most recent MAX_ITEMS.
            items = items[-MAX_ITEMS:]
            _write_raw(items)
    return added


def clear_memory() -> None:
    """Erase all stored memory."""
    with _lock:
        _write_raw([])


def format_for_prompt() -> str:
    """Render memory items as a bulleted block for the chat system prompt."""
    items = load_memory()
    if not items:
        return "(no saved memories yet)"
    return "\n".join(f"- {i.get('text', '')}" for i in items)
