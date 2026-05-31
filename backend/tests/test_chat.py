"""Unit tests for follow-up chat (src/agent/chat.py)."""

import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agent import chat
from tests.conftest import parse_sse

# ── extract_memories ─────────────────────────────────────────────────────────


def test_extract_memories_none():
    clean, mems = chat.extract_memories("Just a normal answer.")
    assert clean == "Just a normal answer."
    assert mems == []


def test_extract_memories_single():
    text = "Here is your answer.\n[[MEMORY: User is a clinician]]"
    clean, mems = chat.extract_memories(text)
    assert clean == "Here is your answer."
    assert mems == ["User is a clinician"]


def test_extract_memories_multiple():
    text = "Answer.\n[[MEMORY: fact one]]\n[[MEMORY: fact two]]"
    clean, mems = chat.extract_memories(text)
    assert mems == ["fact one", "fact two"]
    assert "[[MEMORY" not in clean


def test_extract_memories_case_insensitive():
    clean, mems = chat.extract_memories("Hi [[memory: lowercase marker]]")
    assert mems == ["lowercase marker"]


# ── _to_contents role mapping ────────────────────────────────────────────────


def test_to_contents_role_mapping():
    contents = chat._to_contents(
        [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
            {"role": "user", "content": "follow up"},
        ]
    )
    assert [c.role for c in contents] == ["user", "model", "user"]
    assert contents[0].parts[0].text == "hello"


def test_to_contents_skips_empty():
    contents = chat._to_contents(
        [{"role": "user", "content": ""}, {"role": "user", "content": "x"}]
    )
    assert len(contents) == 1


# ── run_chat_streaming (mocked Gemini) ───────────────────────────────────────


def _fake_stream(chunks):
    """Build a fake client whose generate_content_stream yields the given texts."""
    client = MagicMock()
    client.models.generate_content_stream.return_value = iter(
        [SimpleNamespace(text=c) for c in chunks]
    )
    return client


async def _collect(gen):
    return [item async for item in gen]


async def test_streaming_emits_delta_and_done():
    client = _fake_stream(["Hello", ", world", "!"])
    with patch("src.agent.chat.get_client", return_value=client):
        events = parse_sse(
            "".join(
                await _collect(
                    chat.run_chat_streaming(
                        "rs1051730",
                        {"variant_id": "rs1051730"},
                        [{"role": "user", "content": "hi"}],
                    )
                )
            )
        )
    deltas = [e for e in events if e["type"] == "delta"]
    done = [e for e in events if e["type"] == "done"]
    assert "".join(d["data"]["text"] for d in deltas) == "Hello, world!"
    assert len(done) == 1
    assert done[0]["data"]["text"] == "Hello, world!"
    assert done[0]["data"]["memories_added"] == []


async def test_streaming_saves_memory_and_hides_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORY_PATH", str(tmp_path / "memory.json"))
    from src.agent import memory as memory_module

    importlib.reload(memory_module)
    importlib.reload(chat)  # rebind chat.memory to the reloaded module

    client = _fake_stream(["Sure thing. ", "[[MEMORY: ", "User is a clinician]]"])
    with patch("src.agent.chat.get_client", return_value=client):
        events = parse_sse(
            "".join(
                await _collect(
                    chat.run_chat_streaming(
                        "rs1051730", None, [{"role": "user", "content": "I am a clinician"}]
                    )
                )
            )
        )
    # The marker must never appear in any visible delta.
    for e in events:
        if e["type"] == "delta":
            assert "[[" not in e["data"]["text"]
    done = next(e for e in events if e["type"] == "done")
    assert done["data"]["text"] == "Sure thing."
    assert done["data"]["memories_added"] == ["User is a clinician"]
    # And it was persisted.
    assert any(i["text"] == "User is a clinician" for i in memory_module.load_memory())


async def test_streaming_error_emits_error_event():
    client = MagicMock()
    client.models.generate_content_stream.side_effect = RuntimeError("model boom")
    with patch("src.agent.chat.get_client", return_value=client):
        events = parse_sse(
            "".join(
                await _collect(
                    chat.run_chat_streaming("rs1051730", None, [{"role": "user", "content": "hi"}])
                )
            )
        )
    errors = [e for e in events if e["type"] == "error"]
    assert errors and "model boom" in errors[0]["data"]["error"]


# restore the canonical chat module for any later-imported tests
@pytest.fixture(autouse=True, scope="module")
def _reload_chat_after():
    yield
    importlib.reload(chat)
