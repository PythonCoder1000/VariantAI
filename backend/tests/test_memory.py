"""Unit tests for the global memory store (src/agent/memory.py)."""

import importlib
import json

import pytest


@pytest.fixture
def mem(tmp_path, monkeypatch):
    """Fresh memory module pointed at a temp file for each test."""
    monkeypatch.setenv("MEMORY_PATH", str(tmp_path / "memory.json"))
    from src.agent import memory as memory_module

    importlib.reload(memory_module)
    return memory_module


def test_starts_empty(mem):
    assert mem.load_memory() == []
    assert mem.format_for_prompt() == "(no saved memories yet)"


def test_add_and_load(mem):
    added = mem.add_memories(["User is a clinician", "Prefers plain language"])
    assert len(added) == 2
    items = mem.load_memory()
    assert [i["text"] for i in items] == ["User is a clinician", "Prefers plain language"]
    assert all("id" in i and "created_at" in i for i in items)


def test_ids_unique_within_batch(mem):
    added = mem.add_memories(["a", "b", "c"])
    assert len({i["id"] for i in added}) == 3


def test_dedup_case_insensitive(mem):
    mem.add_memories(["User is a clinician"])
    added = mem.add_memories(["user is a clinician", "New fact"])
    assert [a["text"] for a in added] == ["New fact"]
    assert len(mem.load_memory()) == 2


def test_empty_strings_ignored(mem):
    added = mem.add_memories(["", "   ", "real"])
    assert [a["text"] for a in added] == ["real"]


def test_clear(mem):
    mem.add_memories(["x", "y"])
    mem.clear_memory()
    assert mem.load_memory() == []


def test_format_for_prompt(mem):
    mem.add_memories(["fact one", "fact two"])
    out = mem.format_for_prompt()
    assert "- fact one" in out and "- fact two" in out


def test_cap_enforced(mem):
    mem.add_memories([f"fact {i}" for i in range(mem.MAX_ITEMS + 10)])
    assert len(mem.load_memory()) == mem.MAX_ITEMS


def test_item_truncated(mem):
    long_text = "z" * (mem.MAX_ITEM_LEN + 100)
    added = mem.add_memories([long_text])
    assert len(added[0]["text"]) == mem.MAX_ITEM_LEN


def test_corrupt_file_treated_as_empty(mem):
    from pathlib import Path

    Path(mem._memory_path()).write_text("not valid json {{")
    assert mem.load_memory() == []
    # And it recovers on next write.
    mem.add_memories(["recovered"])
    assert [i["text"] for i in mem.load_memory()] == ["recovered"]


def test_persists_to_disk(mem):
    mem.add_memories(["durable fact"])
    on_disk = json.loads(open(mem._memory_path()).read())
    assert on_disk["items"][0]["text"] == "durable fact"
